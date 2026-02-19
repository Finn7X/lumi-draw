"""
FastAPI route definitions for the Image Generation service.

Multi-turn conversation design:
- POST /conversations               — create a new session
- POST /conversations/{id}/messages — send one user turn, get agent reply
- GET  /conversations/{id}/messages — retrieve display history (for page refresh)

Each conversation is isolated by its conversation_id, which is used directly
as LangGraph's thread_id inside the agent service.

Concurrency:
- Blocking agent call is offloaded to a thread pool via run_in_threadpool.
- asyncio.wait_for enforces a per-request timeout (600 s).
- Per-conversation asyncio.Lock prevents concurrent turns on the same session.
"""

import uuid
import asyncio
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from starlette.concurrency import run_in_threadpool

from .schemas import (
    ConversationCreateRequest,
    ConversationCreateResponse,
    ConversationMessageRequest,
    ConversationMessageResponse,
    ConversationMessagesResponse,
    ConversationHistoryMessage,
    HealthResponse,
)
from ..agent.service import ImageGenAgenticService
from ..agent.conversation_store import InMemoryConversationStore, DisplayMessage

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Singletons (one per process)
# ---------------------------------------------------------------------------

_service: ImageGenAgenticService | None = None
_store: InMemoryConversationStore | None = None

# Per-conversation asyncio locks — must be created and held in async context.
_conversation_locks: dict[str, asyncio.Lock] = {}

AGENT_TIMEOUT = 600.0  # seconds; routes enforce this via asyncio.wait_for


def get_service() -> ImageGenAgenticService:
    global _service
    if _service is None:
        _service = ImageGenAgenticService()
    return _service


def get_store() -> InMemoryConversationStore:
    global _store
    if _store is None:
        _store = InMemoryConversationStore()
    return _store


def _get_lock(conversation_id: str) -> asyncio.Lock:
    """Return (or lazily create) the per-conversation asyncio.Lock."""
    if conversation_id not in _conversation_locks:
        _conversation_locks[conversation_id] = asyncio.Lock()
    return _conversation_locks[conversation_id]


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Service health check endpoint."""
    return HealthResponse()


# ---------------------------------------------------------------------------
# Conversation management
# ---------------------------------------------------------------------------

@router.post(
    "/conversations",
    response_model=ConversationCreateResponse,
    tags=["conversation"],
    status_code=201,
)
async def create_conversation(request: ConversationCreateRequest):
    """
    Create a new conversation session.

    The returned conversation_id must be passed with every subsequent message
    to maintain context continuity.
    """
    store = get_store()
    conv = store.create(user_id=request.user_id)
    return ConversationCreateResponse(
        conversation_id=conv.conversation_id,
        created_at=conv.created_at.isoformat(),
    )


@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessageResponse,
    tags=["conversation"],
)
async def send_message(conversation_id: str, request: ConversationMessageRequest):
    """
    Send a user message within an existing conversation and return the agent reply.

    - The agent retains full history (all tool calls, intermediate steps) via
      LangGraph's MemorySaver, keyed by conversation_id.
    - Follow-up messages are interpreted as incremental modifications to the
      previous result, unless the user explicitly requests a fresh start.
    - HTTP 409 is returned if the conversation is already processing a request.
    - HTTP 504 is returned if the agent exceeds the timeout.
    """
    store = get_store()
    service = get_service()

    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found or expired")

    lock = _get_lock(conversation_id)
    if lock.locked():
        raise HTTPException(
            status_code=409,
            detail="Conversation is busy processing a previous request. Please wait.",
        )

    async with lock:
        # Append user message immediately so history is consistent even if agent fails.
        user_msg = DisplayMessage(
            message_id=str(uuid.uuid4()),
            role="user",
            content=request.query,
            image_url=None,
            created_at=datetime.now(timezone.utc),
        )
        store.append_message(conversation_id, user_msg)

        try:
            result_text = await asyncio.wait_for(
                run_in_threadpool(
                    service.generate_image,
                    query=request.query,
                    conversation_id=conversation_id,
                    user_id=request.user_id or "",
                ),
                timeout=AGENT_TIMEOUT,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Agent timeout after %.0fs for conversation %s",
                AGENT_TIMEOUT, conversation_id,
            )
            raise HTTPException(
                status_code=504,
                detail=f"Image generation timed out after {int(AGENT_TIMEOUT)}s. "
                       "Try simplifying the description.",
            )
        except Exception as e:
            logger.error(
                "Unexpected error in conversation %s: %s", conversation_id, e, exc_info=True,
            )
            raise HTTPException(status_code=500, detail=str(e))

        image_url = service.extract_image_url(result_text)
        assistant_msg_id = str(uuid.uuid4())
        assistant_msg = DisplayMessage(
            message_id=assistant_msg_id,
            role="assistant",
            content=result_text,
            image_url=image_url,
            created_at=datetime.now(timezone.utc),
        )
        store.append_message(conversation_id, assistant_msg)

        return ConversationMessageResponse(
            status="success",
            result=result_text,
            conversation_id=conversation_id,
            message_id=assistant_msg_id,
            last_image_url=image_url,
        )


@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=ConversationMessagesResponse,
    tags=["conversation"],
)
async def get_messages(conversation_id: str):
    """
    Retrieve the display message history of a conversation.

    Useful for restoring chat history after a page refresh.
    Returns only user-facing messages (user input + agent final reply);
    internal tool calls and intermediate steps are not included.
    """
    store = get_store()
    conv = store.get(conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="Conversation not found or expired")

    return ConversationMessagesResponse(
        conversation_id=conversation_id,
        turn_count=conv.turn_count,
        messages=[
            ConversationHistoryMessage(
                message_id=m.message_id,
                role=m.role,
                content=m.content,
                image_url=m.image_url,
                created_at=m.created_at.isoformat(),
            )
            for m in conv.messages
        ],
    )

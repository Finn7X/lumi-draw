"""
In-memory conversation store for multi-turn session management.

Stores metadata and frontend-displayable message history per conversation.
The agent's full internal message history (tool calls, intermediate steps)
is managed by LangGraph's MemorySaver, keyed by conversation_id as thread_id.
"""

import uuid
import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class DisplayMessage:
    """A single message suitable for frontend display."""
    message_id: str
    role: str           # "user" | "assistant"
    content: str        # raw user input or agent's final markdown reply
    image_url: str | None
    created_at: datetime


@dataclass
class ConversationState:
    """
    Metadata and display history for one conversation.

    conversation_id is also used directly as LangGraph thread_id —
    no separate thread_id field is needed.
    """
    conversation_id: str
    user_id: str
    created_at: datetime
    updated_at: datetime
    turn_count: int
    last_image_url: str | None
    messages: list[DisplayMessage] = field(default_factory=list)


class InMemoryConversationStore:
    """
    V1: in-process conversation store with TTL-based expiry.

    Not suitable for multi-instance deployments; upgrade to Redis/DB for V2.
    """

    def __init__(self, ttl_seconds: int = 86400):
        self._store: dict[str, ConversationState] = {}
        self._ttl = ttl_seconds
        self._cleanup_task: asyncio.Task | None = None

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def create(self, user_id: str = "") -> ConversationState:
        """Create a new conversation and return it."""
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        conv = ConversationState(
            conversation_id=conv_id,
            user_id=user_id,
            created_at=now,
            updated_at=now,
            turn_count=0,
            last_image_url=None,
        )
        self._store[conv_id] = conv
        logger.info("Conversation created: %s (user=%s)", conv_id, user_id or "anonymous")
        return conv

    def get(self, conversation_id: str) -> ConversationState | None:
        """Return conversation state or None if not found / expired."""
        conv = self._store.get(conversation_id)
        if conv is not None:
            conv.updated_at = datetime.now(timezone.utc)
        return conv

    def append_message(self, conversation_id: str, msg: DisplayMessage) -> None:
        """
        Append a display message to the conversation history.
        Updates turn_count and last_image_url when the assistant responds.
        """
        conv = self._store.get(conversation_id)
        if conv is None:
            raise KeyError(f"Conversation {conversation_id} not found")
        conv.messages.append(msg)
        conv.updated_at = datetime.now(timezone.utc)
        if msg.role == "assistant":
            conv.turn_count += 1
            if msg.image_url:
                conv.last_image_url = msg.image_url

    # ------------------------------------------------------------------
    # TTL cleanup
    # ------------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """Remove conversations that have not been accessed within TTL. Returns count removed."""
        now = datetime.now(timezone.utc)
        expired = [
            cid for cid, conv in self._store.items()
            if (now - conv.updated_at).total_seconds() > self._ttl
        ]
        for cid in expired:
            del self._store[cid]
        if expired:
            logger.info("TTL cleanup: removed %d expired conversations", len(expired))
        return len(expired)

    def start_cleanup_task(self) -> asyncio.Task:
        """
        Start an asyncio background task that runs TTL cleanup every hour.
        Call this from FastAPI lifespan startup.
        """
        async def _loop():
            while True:
                await asyncio.sleep(3600)
                self.cleanup_expired()

        self._cleanup_task = asyncio.create_task(_loop())
        logger.info("Conversation TTL cleanup task started (TTL=%ds)", self._ttl)
        return self._cleanup_task

    def stop_cleanup_task(self) -> None:
        """Cancel the background cleanup task on shutdown."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()

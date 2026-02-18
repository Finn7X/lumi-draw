"""
Pydantic schemas for API request / response models.
"""

from pydantic import BaseModel, Field
from typing import Optional


# ---------------------------------------------------------------------------
# Conversation schemas
# ---------------------------------------------------------------------------

class ConversationCreateRequest(BaseModel):
    """Create a new conversation session."""
    user_id: str = Field(default="", description="Optional user identifier for tracing")


class ConversationCreateResponse(BaseModel):
    """New conversation session."""
    conversation_id: str = Field(..., description="Stable session ID; pass in subsequent messages")
    created_at: str = Field(..., description="ISO 8601 UTC timestamp")


class ConversationMessageRequest(BaseModel):
    """Send a message (user turn) within an existing conversation."""
    query: str = Field(..., description="User instruction or follow-up", min_length=1)
    user_id: str = Field(default="", description="Optional user identifier for tracing")


class ConversationMessageResponse(BaseModel):
    """Result of one agent turn."""
    status: str = Field(..., description="'success' or 'error'")
    result: str = Field(default="", description="Agent reply in markdown (contains image URL)")
    conversation_id: str = Field(..., description="Echo of the conversation ID")
    message_id: str = Field(..., description="UUID of the assistant message just appended")
    last_image_url: Optional[str] = Field(default=None, description="Image URL extracted from result, if any")
    error: Optional[str] = Field(default=None, description="Error message when status='error'")


class ConversationHistoryMessage(BaseModel):
    """One message entry for history display."""
    message_id: str
    role: str = Field(..., description="'user' or 'assistant'")
    content: str
    image_url: Optional[str] = None
    created_at: str = Field(..., description="ISO 8601 UTC timestamp")


class ConversationMessagesResponse(BaseModel):
    """Full display history of a conversation."""
    conversation_id: str
    turn_count: int
    messages: list[ConversationHistoryMessage]


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    service: str = "lumi-draw"

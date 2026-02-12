"""
Pydantic schemas for API request / response models.
"""

from pydantic import BaseModel, Field
from typing import Optional


class ImageGenRequest(BaseModel):
    """Image generation request body."""
    query: str = Field(..., description="User description of the image to generate", min_length=1)
    user_id: str = Field(default="", description="Optional user identifier for tracing")


class ImageGenResponse(BaseModel):
    """Image generation response body."""
    status: str = Field(..., description="Result status: success / error")
    result: str = Field(default="", description="Agent response containing the image URL")
    error: Optional[str] = Field(default=None, description="Error message if failed")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "ok"
    service: str = "lumi-draw"

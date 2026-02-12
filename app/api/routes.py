"""
FastAPI route definitions for the Image Generation service.
"""

import logging

from fastapi import APIRouter, HTTPException

from .schemas import ImageGenRequest, ImageGenResponse, HealthResponse
from ..agent.service import ImageGenAgenticService

logger = logging.getLogger(__name__)

router = APIRouter()

# Singleton service instance
_service: ImageGenAgenticService | None = None


def get_service() -> ImageGenAgenticService:
    """Get or create the singleton service instance."""
    global _service
    if _service is None:
        _service = ImageGenAgenticService()
    return _service


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """Service health check endpoint."""
    return HealthResponse()


@router.post("/generate", response_model=ImageGenResponse, tags=["image"])
async def generate_image(request: ImageGenRequest):
    """
    Generate an image from a natural-language description.

    The agent will autonomously choose HTML or Mermaid rendering,
    perform VL quality checks, and return an image URL.
    """
    try:
        service = get_service()
        result = service.generate_image(
            query=request.query,
            user_id=request.user_id,
        )
        return ImageGenResponse(status="success", result=result)
    except Exception as e:
        logger.error("Image generation failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

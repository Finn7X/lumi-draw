"""
FastAPI application entry point for Lumi Draw service.
"""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI

from .config import get_settings
from .api.routes import router


settings = get_settings()

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup / shutdown hooks."""
    logging.getLogger(__name__).info("Lumi Draw starting up ...")
    yield
    logging.getLogger(__name__).info("Lumi Draw shutting down ...")


app = FastAPI(
    title="Lumi Draw",
    description="LLM-powered agentic image generation service. "
                "Supports HTML and Mermaid rendering with VL quality checks.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(router, prefix="/api/v1")


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=False,
    )

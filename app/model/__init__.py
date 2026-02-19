"""
LLM model configuration module.
"""

from .llm_config import (
    get_main_model,
    get_fallback_models,
)

__all__ = [
    "get_main_model",
    "get_fallback_models",
]

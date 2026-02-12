"""
LLM model configuration - reads all credentials and URLs from Settings.

Primary model : configurable (default minimax-m21)
Fallback model: configurable (default kimi-k2)
"""

import httpx
from langchain_openai import ChatOpenAI

from ..config import get_settings


def _build_http_client() -> httpx.Client:
    """Shared httpx client config: no SSL verify, no proxy, custom timeouts."""
    return httpx.Client(
        verify=False,
        http2=False,
        trust_env=False,
        timeout=httpx.Timeout(connect=10.0, read=120.0, write=30.0, pool=10.0),
    )


def get_primary_model() -> ChatOpenAI:
    """Return the primary ChatOpenAI model instance."""
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_primary_model,
        base_url=s.llm_primary_base_url,
        api_key=s.llm_primary_api_key,
        streaming=True,
        temperature=s.llm_primary_temperature,
        timeout=s.llm_primary_timeout,
        max_retries=s.llm_primary_max_retries,
        http_client=_build_http_client(),
    )


def get_fallback_model() -> ChatOpenAI:
    """Return the fallback ChatOpenAI model instance."""
    s = get_settings()
    return ChatOpenAI(
        model=s.llm_fallback_model,
        base_url=s.llm_fallback_base_url,
        api_key=s.llm_fallback_api_key,
        max_tokens=s.llm_fallback_max_tokens,
        streaming=True,
        temperature=s.llm_fallback_temperature,
        timeout=s.llm_fallback_timeout,
        max_retries=s.llm_fallback_max_retries,
        http_client=_build_http_client(),
    )


# Model priority list
MODEL_PRIORITY_LIST = ["primary", "fallback"]

_MODEL_GETTERS = {
    "primary": get_primary_model,
    "fallback": get_fallback_model,
}


def get_all_models_by_priority() -> list[ChatOpenAI]:
    """Return all model instances ordered by priority."""
    return [getter() for getter in _MODEL_GETTERS.values()]


def get_main_model() -> ChatOpenAI:
    """Return the primary (highest priority) model."""
    return get_primary_model()


def get_fallback_models() -> list[ChatOpenAI]:
    """Return all fallback model instances."""
    return [get_fallback_model()]

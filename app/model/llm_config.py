"""
LLM model configuration - reads all credentials and URLs from Settings.

Primary model: configurable (default moonshot-v1-128k via Moonshot public API)
"""

import httpx
from langchain_openai import ChatOpenAI

from ..config import get_settings
from .kimi_reasoning_compat import patch_langchain_openai_reasoning_support


def _build_http_client() -> httpx.Client:
    """Shared httpx client config: no SSL verify, no proxy, custom timeouts."""
    return httpx.Client(
        verify=False,
        http2=False,
        trust_env=False,
        timeout=httpx.Timeout(connect=10.0, read=600.0, write=600.0, pool=10.0),
    )


def get_primary_model() -> ChatOpenAI:
    """Return the primary ChatOpenAI model instance."""
    s = get_settings()
    patch_langchain_openai_reasoning_support()

    is_kimi_25 = s.llm_primary_model.lower().startswith("kimi-k2.5")
    kwargs = dict(
        model=s.llm_primary_model,
        base_url=s.llm_primary_base_url,
        api_key=s.llm_primary_api_key,
        # Kimi thinking + tool calling is more stable with non-streaming invoke.
        streaming=not is_kimi_25,
        temperature=s.llm_primary_temperature,
        timeout=s.llm_primary_timeout,
        max_retries=s.llm_primary_max_retries,
        http_client=_build_http_client(),
    )

    if is_kimi_25:
        kwargs["extra_body"] = {
            "thinking": {
                "type": "enabled" if s.llm_primary_thinking_enabled else "disabled"
            }
        }

    if s.llm_primary_max_tokens is not None:
        kwargs["max_tokens"] = s.llm_primary_max_tokens
    return ChatOpenAI(**kwargs)


def get_main_model() -> ChatOpenAI:
    """Return the primary (highest priority) model."""
    return get_primary_model()


def get_fallback_models() -> list[ChatOpenAI]:
    """No fallback models configured."""
    return []

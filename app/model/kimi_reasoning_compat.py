"""
Compatibility helpers for Kimi thinking mode with LangChain OpenAI adapter.

Moonshot's Kimi thinking models may require `reasoning_content` to be present
in assistant tool-call messages across multi-turn requests. Some
langchain-openai versions do not preserve this field when converting messages
between provider payloads and LangChain message objects.

This module monkey-patches conversion helpers in langchain-openai to:
1) keep `reasoning_content` when reading provider responses, and
2) send it back on subsequent assistant tool-call messages.
"""

from __future__ import annotations

import logging
from typing import Any, Mapping

logger = logging.getLogger(__name__)

_PATCH_FLAG = "_lumi_kimi_reasoning_patch_applied"


def patch_langchain_openai_reasoning_support() -> None:
    """
    Patch langchain-openai message conversion to preserve `reasoning_content`.

    The patch is idempotent and safe to call multiple times.
    """
    try:
        from langchain_core.messages import AIMessage
        from langchain_openai.chat_models import base as openai_chat_base
    except Exception as e:
        logger.warning("Skip Kimi reasoning compatibility patch: %s", e)
        return

    if getattr(openai_chat_base, _PATCH_FLAG, False):
        return

    original_convert_from_dict = getattr(openai_chat_base, "_convert_dict_to_message", None)
    original_convert_to_dict = getattr(openai_chat_base, "_convert_message_to_dict", None)
    if not callable(original_convert_from_dict) or not callable(original_convert_to_dict):
        logger.warning("Skip Kimi reasoning compatibility patch: converter not found")
        return

    def _patched_convert_dict_to_message(_dict: Mapping[str, Any]):  # type: ignore[no-untyped-def]
        msg = original_convert_from_dict(_dict)
        if isinstance(msg, AIMessage):
            reasoning_content = _dict.get("reasoning_content")
            if reasoning_content is not None:
                msg.additional_kwargs["reasoning_content"] = str(reasoning_content)
        return msg

    def _patched_convert_message_to_dict(message, *args, **kwargs):  # type: ignore[no-untyped-def]
        msg_dict = original_convert_to_dict(message, *args, **kwargs)
        if isinstance(message, AIMessage):
            reasoning_content = message.additional_kwargs.get("reasoning_content")
            if reasoning_content is not None:
                msg_dict["reasoning_content"] = str(reasoning_content)
            elif msg_dict.get("tool_calls"):
                # Keep schema-compatible field for thinking+tool-call turns even
                # when upstream parser did not populate reasoning_content.
                msg_dict["reasoning_content"] = ""
        return msg_dict

    openai_chat_base._convert_dict_to_message = _patched_convert_dict_to_message
    openai_chat_base._convert_message_to_dict = _patched_convert_message_to_dict
    setattr(openai_chat_base, _PATCH_FLAG, True)

    logger.info("Applied Kimi reasoning compatibility patch for langchain-openai")

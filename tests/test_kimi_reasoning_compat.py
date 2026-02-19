"""
Tests for Kimi thinking compatibility patch.
"""

from app.model.kimi_reasoning_compat import patch_langchain_openai_reasoning_support


def test_convert_dict_to_message_keeps_reasoning_content():
    from langchain_openai.chat_models import base as openai_chat_base

    patch_langchain_openai_reasoning_support()

    raw_assistant_message = {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "draw", "arguments": "{}"},
            }
        ],
        "reasoning_content": "step-by-step thinking",
    }

    message = openai_chat_base._convert_dict_to_message(raw_assistant_message)
    assert message.additional_kwargs["reasoning_content"] == "step-by-step thinking"


def test_convert_message_to_dict_sends_reasoning_content():
    from langchain_core.messages import AIMessage
    from langchain_openai.chat_models import base as openai_chat_base

    patch_langchain_openai_reasoning_support()

    message = AIMessage(
        content="",
        tool_calls=[{"name": "draw", "args": {}, "id": "call_1", "type": "tool_call"}],
        additional_kwargs={"reasoning_content": "carry to next turn"},
    )

    payload = openai_chat_base._convert_message_to_dict(message)
    assert payload["reasoning_content"] == "carry to next turn"


def test_convert_message_to_dict_fills_empty_reasoning_for_tool_calls():
    from langchain_core.messages import AIMessage
    from langchain_openai.chat_models import base as openai_chat_base

    patch_langchain_openai_reasoning_support()

    message = AIMessage(
        content="",
        tool_calls=[{"name": "draw", "args": {}, "id": "call_1", "type": "tool_call"}],
    )

    payload = openai_chat_base._convert_message_to_dict(message)
    assert "reasoning_content" in payload
    assert payload["reasoning_content"] == ""

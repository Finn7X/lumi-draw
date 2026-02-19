"""
Image Generation Agentic Service

Core service class that orchestrates the LLM agent to generate images
from natural-language descriptions using HTML Native rendering,
with VL model quality checks.

Multi-turn design:
- One MemorySaver instance is shared across all conversations (per process).
- Each conversation is isolated by its conversation_id, used directly as
  LangGraph's thread_id.
- Timeout is handled at the async route layer via asyncio.wait_for;
  this module does NOT use signal.SIGALRM.
"""

import re
import os
import logging
from datetime import datetime

from langgraph.checkpoint.memory import MemorySaver
from langchain.agents.middleware import (
    ModelFallbackMiddleware, SummarizationMiddleware,
    ContextEditingMiddleware, ClearToolUsesEdit,
)
from langchain.agents import create_agent
from deepagents.middleware.patch_tool_calls import PatchToolCallsMiddleware
from langchain.messages import HumanMessage

from ..config import get_settings
from ..model import get_main_model, get_fallback_models
from ..tool import generate_html_image, check_image_quality
from .prompt import get_system_prompt

logger = logging.getLogger(__name__)

# Inject Langfuse env vars from config (required before importing the handler)
_settings = get_settings()
if _settings.langfuse_secret_key:
    os.environ.setdefault("LANGFUSE_SECRET_KEY", _settings.langfuse_secret_key)
if _settings.langfuse_public_key:
    os.environ.setdefault("LANGFUSE_PUBLIC_KEY", _settings.langfuse_public_key)
if _settings.langfuse_host:
    os.environ.setdefault("LANGFUSE_HOST", _settings.langfuse_host)

from langfuse.langchain import CallbackHandler as LangfuseCallbackHandler

# Regex to extract the first markdown image URL from agent output
_IMAGE_URL_RE = re.compile(r'!\[[^\]]*\]\(([^)]+)\)')


class ImageGenAgenticService:
    """
    Image Generation Agentic Service (HTML Native).

    - Receives a user description and generates images via HTML rendering.
    - Built-in VL model quality check.
    - Multi-model fallback mechanism.
    - Langfuse tracing (tag: ImageGen).
    - Multi-turn: one MemorySaver shared across conversations, isolated by thread_id.
    """

    def __init__(self, service_name: str = "image_gen"):
        self.service_name = service_name
        self.memory = MemorySaver()
        self.agent = self._create_agent()
        logger.info("[%s] Service initialized", self.service_name)

    def _create_agent(self):
        """Create and return a configured LangGraph agent using the shared MemorySaver."""
        model = get_main_model()
        fallback_models = get_fallback_models()

        logger.info(
            "[%s] Primary model: %s, fallback count: %d",
            self.service_name, model.model_name, len(fallback_models),
        )

        tools = [generate_html_image, check_image_quality]
        if get_settings().agent_enable_mermaid:
            try:
                from ..tool import generate_mermaid_image
                tools.insert(1, generate_mermaid_image)
                logger.info("[%s] Mermaid tool enabled (migration flag)", self.service_name)
            except ImportError:
                logger.warning("[%s] Mermaid flag enabled but module not found", self.service_name)
        system_prompt = get_system_prompt()

        # Parameters tuned for 128k context models.
        # A single HTML-rendering turn consumes ~4k-9k tokens.
        # With 128k available, we can hold 10+ turns before needing compression.
        context_editing = ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=50000,   # was 24000: clear old tool outputs only after 50k tokens
                    keep=3,          # was 5: HTML outputs are large; 3 recent turns is enough
                    placeholder="[Earlier tool output cleared]",
                )
            ],
            token_count_method="approximate",
        )

        summarization = SummarizationMiddleware(
            model=model,
            trigger=("tokens", 90000),          # was 26000: only compress near the real limit
            keep=("tokens", 25000),             # was 8000: retain more recent context
            trim_tokens_to_summarize=30000,     # was 8000: compress larger chunks at once
            summary_prefix="[History summary] ",
        )

        middleware = [
            PatchToolCallsMiddleware(),
            context_editing,
            summarization,
        ]
        if fallback_models:
            middleware.append(ModelFallbackMiddleware(*fallback_models))

        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=self.memory,
            middleware=middleware,
        ).with_config({"recursion_limit": 50})

        logger.info(
            "[%s] Agent created, tools: %s, middleware: %d",
            self.service_name, [t.name for t in tools], len(middleware),
        )
        return agent

    @staticmethod
    def _extract_final_output(result: dict, conversation_id: str) -> str:
        """Extract the last AI message (without tool_calls) from agent results."""
        messages = result.get("messages", [])
        for msg in reversed(messages):
            if (
                hasattr(msg, "type") and msg.type == "ai"
                and hasattr(msg, "content") and msg.content
                and not getattr(msg, "tool_calls", None)
            ):
                content = msg.content.strip()
                if content:
                    logger.info(
                        "[%s] Extracted final output (%d chars)",
                        conversation_id, len(content),
                    )
                    return content

        logger.warning("[%s] No valid final output found", conversation_id)
        return ""

    @staticmethod
    def extract_image_url(text: str) -> str | None:
        """
        Parse the first markdown image URL from agent output text.

        Agent reply format: "已为您生成图片：\\n[desc]\\n![desc](url)"
        Returns the URL string, or None if not found.
        """
        m = _IMAGE_URL_RE.search(text)
        return m.group(1) if m else None

    def generate_image(
        self,
        query: str,
        conversation_id: str,
        user_id: str = "",
    ) -> str:
        """
        Execute one turn of the image generation workflow.

        Args:
            query: Natural-language image description or follow-up instruction.
            conversation_id: Stable conversation identifier; used as LangGraph thread_id
                             so that history is preserved across turns.
            user_id: Optional user identifier for Langfuse tracing.

        Returns:
            Agent response string containing the image URL in markdown format.

        Note:
            Timeout is NOT handled here. The caller (async route) should wrap
            this call in asyncio.wait_for(run_in_threadpool(...), timeout=...).
        """
        session_id = (
            f"{self.service_name}_{user_id}"
            if user_id
            else f"{self.service_name}_anonymous"
        )

        logger.info(
            "[%s][%s] ===== Start image generation =====",
            self.service_name, conversation_id,
        )
        logger.info("[%s][%s] Query: %s", self.service_name, conversation_id, query)

        callbacks = []
        settings = get_settings()
        if settings.langfuse_secret_key and settings.langfuse_public_key:
            try:
                langfuse_handler = LangfuseCallbackHandler()
                callbacks.append(langfuse_handler)
                logger.info(
                    "[%s][%s] Langfuse tracing enabled",
                    self.service_name, conversation_id,
                )
            except Exception as e:
                logger.warning(
                    "[%s][%s] Langfuse init failed: %s",
                    self.service_name, conversation_id, e,
                )

        messages = [HumanMessage(content=query)]

        config = {
            "configurable": {"thread_id": conversation_id},
            "callbacks": callbacks,
            "metadata": {
                "langfuse_user_id": user_id or "anonymous",
                "langfuse_session_id": session_id,
                "langfuse_tags": ["ImageGen", "image_gen_agent"],
            },
        }

        logger.info("[%s][%s] Agent executing ...", self.service_name, conversation_id)
        start_time = datetime.now()

        try:
            result = self.agent.invoke({"messages": messages}, config=config)
        except Exception as e:
            error_type = type(e).__name__
            elapsed = (datetime.now() - start_time).total_seconds()
            logger.error(
                "[%s][%s] Error after %.2fs: %s - %s",
                self.service_name, conversation_id, elapsed, error_type, e,
                exc_info=True,
            )
            if "RateLimitError" in error_type:
                return "LLM rate limit exceeded. Please retry later."
            return "Image generation service encountered an error. Please retry later."

        elapsed = (datetime.now() - start_time).total_seconds()
        logger.info(
            "[%s][%s] Agent finished in %.2fs",
            self.service_name, conversation_id, elapsed,
        )

        final_output = self._extract_final_output(result, conversation_id)

        tool_calls_count = 0
        tool_names_used: list[str] = []
        for msg in result.get("messages", []):
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_calls_count += 1
                    name = tc.get("name", "unknown")
                    if name not in tool_names_used:
                        tool_names_used.append(name)

        logger.info(
            "[%s][%s] Tool calls: %d, tools: %s",
            self.service_name, conversation_id, tool_calls_count, tool_names_used or "none",
        )
        logger.info(
            "[%s][%s] ===== Done (%.2fs) =====",
            self.service_name, conversation_id, elapsed,
        )

        if not final_output:
            logger.warning(
                "[%s][%s] Agent finished but produced no output",
                self.service_name, conversation_id,
            )
            return "Image generation agent completed but produced no output."

        return final_output

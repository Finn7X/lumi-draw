"""
Image Generation Agentic Service

Core service class that orchestrates the LLM agent to generate images
from natural-language descriptions using HTML or Mermaid rendering,
with VL model quality checks.
"""

import os
import logging
import hashlib
import signal
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
from ..tool import generate_html_image, generate_mermaid_image, check_image_quality
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


class ImageGenAgenticService:
    """
    Image Generation Agentic Service.

    - Receives a user description and autonomously selects HTML or Mermaid rendering.
    - Built-in VL model quality check.
    - Multi-model fallback mechanism.
    - Langfuse tracing (tag: ImageGen).
    """

    def __init__(self, service_name: str = "image_gen"):
        self.service_name = service_name
        logger.info("[%s] Service initialized", self.service_name)

    def _create_agent(self):
        """Create and return a configured LangGraph agent."""
        memory = MemorySaver()

        model = get_main_model()
        fallback_models = get_fallback_models()

        logger.info(
            "[%s] Primary model: %s, fallback count: %d",
            self.service_name, model.model_name, len(fallback_models),
        )

        tools = [generate_html_image, generate_mermaid_image, check_image_quality]
        system_prompt = get_system_prompt()

        summarization = SummarizationMiddleware(
            model=model,
            trigger=("tokens", 26000),
            keep=("tokens", 8000),
            trim_tokens_to_summarize=8000,
            summary_prefix="[History summary] ",
        )

        fallback = ModelFallbackMiddleware(*fallback_models)

        context_editing = ContextEditingMiddleware(
            edits=[
                ClearToolUsesEdit(
                    trigger=24000,
                    keep=5,
                    placeholder="[Earlier tool output cleared]",
                )
            ],
            token_count_method="approximate",
        )

        middleware = [
            PatchToolCallsMiddleware(),
            context_editing,
            summarization,
            fallback,
        ]

        agent = create_agent(
            model=model,
            tools=tools,
            system_prompt=system_prompt,
            checkpointer=memory,
            middleware=middleware,
        ).with_config({"recursion_limit": 50})

        logger.info(
            "[%s] Agent created, tools: %s, middleware: %d",
            self.service_name, [t.name for t in tools], len(middleware),
        )
        return agent

    @staticmethod
    def _extract_final_output(result: dict, thread_id: str) -> str:
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
                    logger.info("[%s] Extracted final output (%d chars)", thread_id, len(content))
                    return content

        logger.warning("[%s] No valid final output found", thread_id)
        return ""

    def generate_image(self, query: str, user_id: str = "") -> str:
        """
        Execute the full image generation workflow.

        Args:
            query: Natural-language image description.
            user_id: Optional user identifier for Langfuse tracing.

        Returns:
            Agent response string containing the image URL.
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            query_hash = hashlib.md5(query.encode("utf-8")).hexdigest()[:8]
            thread_id = f"{timestamp}_{query_hash}"
            session_id = (
                f"{self.service_name}_{user_id}"
                if user_id
                else f"{self.service_name}_anonymous"
            )

            logger.info("[%s][%s] ===== Start image generation =====", self.service_name, thread_id)
            logger.info("[%s][%s] Query: %s", self.service_name, thread_id, query)

            # Initialize Langfuse handler only if configured
            callbacks = []
            settings = get_settings()
            if settings.langfuse_secret_key and settings.langfuse_public_key:
                try:
                    langfuse_handler = LangfuseCallbackHandler()
                    callbacks.append(langfuse_handler)
                    logger.info("[%s][%s] Langfuse tracing enabled", self.service_name, thread_id)
                except Exception as e:
                    logger.warning("[%s][%s] Langfuse init failed: %s", self.service_name, thread_id, e)

            agent = self._create_agent()
            messages = [HumanMessage(content=query)]

            logger.info("[%s][%s] Agent executing ...", self.service_name, thread_id)
            start_time = datetime.now()

            config = {
                "configurable": {"thread_id": thread_id},
                "callbacks": callbacks,
                "metadata": {
                    "langfuse_user_id": user_id or "anonymous",
                    "langfuse_session_id": session_id,
                    "langfuse_tags": ["ImageGen", "image_gen_agent"],
                },
            }

            # Guard against runaway agent loops with a hard timeout
            agent_timeout = 120  # seconds

            def _timeout_handler(signum, frame):
                raise TimeoutError(f"Agent execution exceeded {agent_timeout}s limit")

            old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
            signal.alarm(agent_timeout)
            try:
                result = agent.invoke({"messages": messages}, config=config)
            finally:
                signal.alarm(0)
                signal.signal(signal.SIGALRM, old_handler)

            elapsed = (datetime.now() - start_time).total_seconds()
            logger.info("[%s][%s] Agent finished in %.2fs", self.service_name, thread_id, elapsed)

            final_output = self._extract_final_output(result, thread_id)

            # Tool-call statistics
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
                self.service_name, thread_id, tool_calls_count, tool_names_used or "none",
            )
            logger.info(
                "[%s][%s] ===== Done (%.2fs) =====", self.service_name, thread_id, elapsed,
            )

            if not final_output:
                logger.warning("[%s][%s] Agent finished but produced no output", self.service_name, thread_id)
                return "Image generation agent completed but produced no output."

            return final_output

        except TimeoutError as e:
            tid = locals().get("thread_id", "unknown")
            elapsed = (datetime.now() - start_time).total_seconds() if "start_time" in locals() else 0
            logger.warning("[%s][%s] Agent timed out after %.1fs: %s", self.service_name, tid, elapsed, e)
            return "图片生成超时，请尝试简化描述或拆分为更小的任务。"

        except Exception as e:
            error_type = type(e).__name__
            tid = locals().get("thread_id", "unknown")
            logger.error("[%s][%s] Error: %s - %s", self.service_name, tid, error_type, e, exc_info=True)

            if "RateLimitError" in error_type:
                return "LLM rate limit exceeded. Please retry later."

            return "Image generation service encountered an error. Please retry later."

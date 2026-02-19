"""
Centralized configuration management

All configuration values are read from environment variables,
with sensible defaults for development.
"""

import os
from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    # --- FastAPI ---
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "info"

    # --- Primary LLM ---
    llm_primary_model: str = "minimax-m21"
    llm_primary_base_url: str = "http://10.220.77.197:9506/v1"
    llm_primary_api_key: str = "EMPTY"
    llm_primary_temperature: float = 0.2
    llm_primary_timeout: int = 60
    llm_primary_max_retries: int = 1

    # --- Fallback LLM ---
    llm_fallback_model: str = "Kimi-K2-Instruct"
    llm_fallback_base_url: str = "https://maas-apigateway.dt.zte.com.cn/model/kimi-k2/v1"
    llm_fallback_api_key: str = ""
    llm_fallback_max_tokens: int = 32000
    llm_fallback_temperature: float = 0.2
    llm_fallback_timeout: int = 60
    llm_fallback_max_retries: int = 1

    # --- VL Quality Check Model ---
    vl_model_url: str = "http://10.220.77.197:9503/v1/chat/completions"
    vl_model_name: str = "Qwen3-VL-30B"
    vl_quality_threshold: int = 7

    # --- Langfuse ---
    langfuse_secret_key: str = ""
    langfuse_public_key: str = ""
    langfuse_host: str = ""

    # --- Image Upload ---
    image_remote_host: str = "10.220.77.197"
    image_remote_dir: str = "/home/ccn-a/images/"
    image_local_dir: str = "/home/ccn-a/images/"
    image_url_base: str = "http://10.220.77.197/images/"
    image_sftp_username: str = "ccn-a"

    # --- Renderer ---
    render_output_dir: str = "/tmp/image_gen"
    render_html_mode: str = "enhanced_web"  # pure_css | enhanced_web
    render_allowed_hosts: str = "cdn.jsdelivr.net,unpkg.com,cdnjs.cloudflare.com"
    render_ready_timeout_ms: int = 12000
    render_block_external_images: bool = True
    render_use_local_echarts: bool = False  # Use local ECharts bundle instead of CDN

    # --- Mermaid Migration ---
    # Feature flag for Mermaid tool. Defaults to False (HTML Native mode).
    # Set to True only during migration window if rollback is needed.
    # Requires service restart to take effect (Settings is cached via @lru_cache).
    # Note: Mermaid code has been removed; rollback requires git revert.
    agent_enable_mermaid: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache()
def get_settings() -> Settings:
    """Return cached Settings instance (singleton)."""
    return Settings()

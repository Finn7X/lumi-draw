"""
Playwright rendering engine.

Provides HTML and Mermaid code to PNG image rendering.
Uses headless Chromium, Docker-compatible.
"""

import os
import uuid
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)


def _ensure_output_dir() -> str:
    """Ensure the rendering output directory exists and return its path."""
    output_dir = get_settings().render_output_dir
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def render_html_to_image(html_content: str, viewport_width: int = 1200) -> dict:
    """
    Render HTML content to a PNG image.

    Args:
        html_content: Complete HTML code.
        viewport_width: Viewport width in pixels (default 1200).

    Returns:
        dict with {status, local_path, width, height} or {status, error}.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "error",
            "error": "playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    output_dir = _ensure_output_dir()
    filename = f"{uuid.uuid4().hex}.png"
    local_path = os.path.join(output_dir, filename)

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            page = browser.new_page(viewport={"width": viewport_width, "height": 800})
            page.set_content(html_content, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(500)
            page.screenshot(path=local_path, full_page=True)

            dimensions = page.evaluate("""() => ({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight
            })""")

            browser.close()

        logger.info("[renderer] HTML done: %s (%dx%d)", local_path, dimensions["width"], dimensions["height"])
        return {
            "status": "success",
            "local_path": local_path,
            "width": dimensions["width"],
            "height": dimensions["height"],
        }

    except Exception as e:
        logger.error("[renderer] HTML render failed: %s", e, exc_info=True)
        return {"status": "error", "error": f"HTML render failed: {e}"}


def render_mermaid_to_image(mermaid_code: str, theme: str = "default") -> dict:
    """
    Render Mermaid diagram code to a PNG image.

    Args:
        mermaid_code: Mermaid diagram source code.
        theme: Mermaid theme (default / dark / forest / neutral).

    Returns:
        dict with {status, local_path, width, height} or {status, error}.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return {
            "status": "error",
            "error": "playwright not installed. Run: pip install playwright && playwright install chromium",
        }

    settings = get_settings()
    output_dir = _ensure_output_dir()
    filename = f"{uuid.uuid4().hex}.png"
    local_path = os.path.join(output_dir, filename)

    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            margin: 0;
            padding: 20px;
            background: white;
            font-family: "Microsoft YaHei", "SimHei", "PingFang SC", sans-serif;
            display: flex;
            justify-content: center;
        }}
        #mermaid-container {{
            display: inline-block;
        }}
    </style>
</head>
<body>
    <div id="mermaid-container">
        <pre class="mermaid">
{mermaid_code}
        </pre>
    </div>
    <script src="{settings.mermaid_cdn_url}"></script>
    <script>
        mermaid.initialize({{
            startOnLoad: true,
            theme: '{theme}',
            securityLevel: 'loose',
            fontFamily: '"Microsoft YaHei", "SimHei", "PingFang SC", sans-serif'
        }});
    </script>
</body>
</html>"""

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                ],
            )
            page = browser.new_page(viewport={"width": 1400, "height": 800})
            page.set_content(html_template, wait_until="networkidle", timeout=30000)

            try:
                page.wait_for_selector("svg", timeout=30000)
            except Exception:
                logger.warning("[renderer] Mermaid SVG selector timeout, continuing ...")

            page.wait_for_timeout(1000)
            page.screenshot(path=local_path, full_page=True)

            dimensions = page.evaluate("""() => ({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight
            })""")

            browser.close()

        logger.info("[renderer] Mermaid done: %s (%dx%d)", local_path, dimensions["width"], dimensions["height"])
        return {
            "status": "success",
            "local_path": local_path,
            "width": dimensions["width"],
            "height": dimensions["height"],
        }

    except Exception as e:
        logger.error("[renderer] Mermaid render failed: %s", e, exc_info=True)
        return {"status": "error", "error": f"Mermaid render failed: {e}"}

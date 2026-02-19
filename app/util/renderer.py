"""
Playwright rendering engine.

Provides HTML code to PNG image rendering.
Uses headless Chromium, Docker-compatible.
"""

import os
import uuid
import logging

from ..config import get_settings

logger = logging.getLogger(__name__)

# Minimum file size (bytes) for a valid rendered image.
# A blank 1200x800 white PNG is ~4-5KB; anything meaningful is larger.
_MIN_IMAGE_SIZE = 8000


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

            # Capture console errors for diagnostics
            console_errors: list[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            page.set_content(html_content, wait_until="networkidle", timeout=30000)

            # Wait for DOM to be fully painted
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(800)

            # Check if the page has any visible content
            content_check = page.evaluate("""() => {
                const body = document.body;
                if (!body) return { hasContent: false, reason: 'no body element' };
                const text = body.innerText.trim();
                const children = body.children.length;
                const images = document.querySelectorAll('img, svg, canvas').length;
                // Check if body has any meaningful visible elements
                const visibleElements = document.querySelectorAll('div, p, h1, h2, h3, h4, h5, h6, span, table, ul, ol, section, article, header, nav, main, footer, aside');
                let visibleCount = 0;
                for (const el of visibleElements) {
                    const rect = el.getBoundingClientRect();
                    const style = window.getComputedStyle(el);
                    if (rect.width > 0 && rect.height > 0 && style.display !== 'none' && style.visibility !== 'hidden') {
                        visibleCount++;
                    }
                }
                return {
                    hasContent: text.length > 0 || images > 0 || visibleCount > 2,
                    textLength: text.length,
                    childCount: children,
                    imageCount: images,
                    visibleCount: visibleCount
                };
            }""")

            if not content_check.get("hasContent", True):
                browser.close()
                errors_info = "; ".join(console_errors[:5]) if console_errors else "none"
                logger.warning(
                    "[renderer] HTML rendered blank page. Console errors: %s | Content check: %s | HTML snippet: %s",
                    errors_info, content_check, html_content[:500],
                )
                return {
                    "status": "error",
                    "error": (
                        f"HTML rendered a blank page (no visible content). "
                        f"Console errors: [{errors_info}]. "
                        f"Possible causes: external JS/CSS dependencies that cannot be loaded, "
                        f"JavaScript errors, or content hidden by CSS. "
                        f"Please rewrite using pure HTML+CSS without any external libraries."
                    ),
                }

            page.screenshot(path=local_path, full_page=True)

            dimensions = page.evaluate("""() => ({
                width: document.documentElement.scrollWidth,
                height: document.documentElement.scrollHeight
            })""")

            browser.close()

        # Secondary check: verify the image file is not suspiciously small (blank)
        file_size = os.path.getsize(local_path)
        if file_size < _MIN_IMAGE_SIZE:
            logger.warning(
                "[renderer] Image file too small (%d bytes), likely blank. HTML snippet: %s",
                file_size, html_content[:300],
            )
            return {
                "status": "error",
                "error": (
                    f"Rendered image is likely blank ({file_size} bytes, expected >={_MIN_IMAGE_SIZE}). "
                    f"Please ensure the HTML contains visible content rendered with pure CSS, "
                    f"without relying on external JavaScript libraries (Chart.js, ECharts, etc.)."
                ),
            }

        if console_errors:
            logger.warning("[renderer] Console errors during render: %s", console_errors[:5])

        logger.info("[renderer] HTML done: %s (%dx%d, %d bytes)", local_path, dimensions["width"], dimensions["height"], file_size)
        return {
            "status": "success",
            "local_path": local_path,
            "width": dimensions["width"],
            "height": dimensions["height"],
        }

    except Exception as e:
        logger.error("[renderer] HTML render failed: %s", e, exc_info=True)
        return {"status": "error", "error": f"HTML render failed: {e}"}



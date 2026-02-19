"""
Playwright rendering engine.

Provides HTML code to PNG image rendering with two modes:
- pure_css: No JavaScript allowed (legacy mode).
- enhanced_web: Allows controlled JS execution (ECharts etc.) with
  CDN whitelist, ready-signal protocol, and local bundle fallback.

Uses headless Chromium, Docker-compatible.
"""

import os
import uuid
import logging
from urllib.parse import urlparse

from ..config import get_settings

logger = logging.getLogger(__name__)

# Minimum file size (bytes) for a valid rendered image.
# A blank 1200x800 white PNG is ~4-5KB; anything meaningful is larger.
_MIN_IMAGE_SIZE = 8000

# Path to local ECharts bundle (fallback for air-gapped environments).
_ECHARTS_LOCAL_PATH = os.path.join(os.path.dirname(__file__), "..", "static", "echarts.min.js")
_echarts_local_cache: bytes | None = None


def _ensure_output_dir() -> str:
    """Ensure the rendering output directory exists and return its path."""
    output_dir = get_settings().render_output_dir
    os.makedirs(output_dir, exist_ok=True)
    return output_dir


def _load_local_echarts() -> bytes | None:
    """Load the local ECharts bundle into memory (cached)."""
    global _echarts_local_cache
    if _echarts_local_cache is not None:
        return _echarts_local_cache
    path = os.path.normpath(_ECHARTS_LOCAL_PATH)
    if os.path.exists(path):
        with open(path, "rb") as f:
            _echarts_local_cache = f.read()
        logger.info("[renderer] Local ECharts bundle loaded (%d bytes)", len(_echarts_local_cache))
        return _echarts_local_cache
    logger.warning("[renderer] Local ECharts bundle not found at %s", path)
    return None


def _detect_enhanced_content(html_content: str) -> bool:
    """Heuristic: does the HTML reference JS libraries that need enhanced mode?"""
    indicators = ["echarts", "setOption", "__LUMI_RENDER_DONE__", "<script"]
    lower = html_content.lower()
    return any(ind.lower() in lower for ind in indicators)


def render_html_to_image(
    html_content: str,
    viewport_width: int = 1200,
    enhanced: bool | None = None,
) -> dict:
    """
    Render HTML content to a PNG image.

    Args:
        html_content: Complete HTML code.
        viewport_width: Viewport width in pixels (default 1200).
        enhanced: Force enhanced_web mode (True/False), or None for auto-detect
                  based on config + HTML content heuristics.

    Returns:
        dict with {status, local_path, width, height} or {status, error, error_code}.
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

    # Determine rendering mode
    if enhanced is None:
        if settings.render_html_mode == "enhanced_web":
            use_enhanced = _detect_enhanced_content(html_content)
        else:
            use_enhanced = False
    else:
        use_enhanced = enhanced

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

            # --- Enhanced mode: set up network interception ---
            blocked_requests: list[str] = []
            if use_enhanced:
                allowed_hosts = set(h.strip() for h in settings.render_allowed_hosts.split(",") if h.strip())
                echarts_bundle = _load_local_echarts() if settings.render_use_local_echarts else None

                def _handle_route(route):
                    url = route.request.url
                    # Always allow data:/blob:/about: URLs
                    if url.startswith(("data:", "blob:", "about:")):
                        route.continue_()
                        return

                    parsed = urlparse(url)
                    host = parsed.netloc

                    # Same-origin (no host = inline content from setContent)
                    if not host:
                        route.continue_()
                        return

                    # Local ECharts bundle intercept
                    if echarts_bundle and "echarts" in url and url.endswith(".js"):
                        route.fulfill(
                            content_type="application/javascript",
                            body=echarts_bundle,
                        )
                        logger.debug("[renderer] Served local ECharts bundle for %s", url)
                        return

                    # Whitelist check
                    if host in allowed_hosts:
                        route.continue_()
                        return

                    # Block external images if configured
                    if settings.render_block_external_images and route.request.resource_type == "image":
                        blocked_requests.append(f"[blocked-image] {url}")
                        route.abort()
                        return

                    # Allow other resources but log them
                    blocked_requests.append(f"[unwhitelisted] {url}")
                    route.continue_()

                page.route("**/*", _handle_route)

                logger.info(
                    "[renderer] Enhanced mode: allowed_hosts=%s, local_echarts=%s",
                    allowed_hosts, echarts_bundle is not None,
                )

            # --- Load content ---
            if use_enhanced:
                page.set_content(html_content, wait_until="domcontentloaded", timeout=15000)
            else:
                page.set_content(html_content, wait_until="networkidle", timeout=30000)
                page.wait_for_load_state("domcontentloaded")

            # --- Wait strategy ---
            if use_enhanced:
                # Wait for application-level ready signal
                ready_signal_found = False
                try:
                    page.wait_for_function(
                        "() => window.__LUMI_RENDER_DONE__ === true",
                        timeout=settings.render_ready_timeout_ms,
                    )
                    ready_signal_found = True
                    logger.debug("[renderer] Ready signal received")
                except Exception:
                    logger.warning("[renderer] Ready signal timeout (%dms), trying fallback selectors",
                                   settings.render_ready_timeout_ms)
                    # Fallback: wait for canvas/svg elements (ECharts renders to canvas)
                    try:
                        page.wait_for_selector("canvas, svg.echarts-svg, [_echarts_instance_]", timeout=5000)
                        logger.debug("[renderer] Fallback selector found")
                    except Exception:
                        # Final fallback: fixed wait
                        page.wait_for_timeout(2000)
                        logger.warning("[renderer] Fallback selector timeout, using fixed wait")
            else:
                page.wait_for_timeout(800)

            # --- Content check ---
            content_check = page.evaluate("""() => {
                const body = document.body;
                if (!body) return { hasContent: false, reason: 'no body element' };
                const text = body.innerText.trim();
                const children = body.children.length;
                const images = document.querySelectorAll('img, svg, canvas').length;
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
                blocked_info = "; ".join(blocked_requests[:5]) if blocked_requests else "none"
                logger.warning(
                    "[renderer] HTML rendered blank page. Console errors: %s | Blocked: %s | Content check: %s | HTML snippet: %s",
                    errors_info, blocked_info, content_check, html_content[:500],
                )

                error_code = "BLANK_PAGE"
                if any("echarts" in e.lower() for e in console_errors):
                    error_code = "LIB_LOAD_FAILED"

                return {
                    "status": "error",
                    "error_code": error_code,
                    "error": (
                        f"HTML rendered a blank page (no visible content). "
                        f"Console errors: [{errors_info}]. "
                        f"Blocked requests: [{blocked_info}]. "
                        f"Please check that all external libraries load correctly "
                        f"and that window.__LUMI_RENDER_DONE__ = true is set after rendering."
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
                "error_code": "FILE_TOO_SMALL",
                "error": (
                    f"Rendered image is likely blank ({file_size} bytes, expected >={_MIN_IMAGE_SIZE}). "
                    f"Please ensure the HTML contains visible content. "
                    f"If using ECharts, ensure the chart container has explicit width/height "
                    f"and window.__LUMI_RENDER_DONE__ = true is set after setOption()."
                ),
            }

        if console_errors:
            logger.warning("[renderer] Console errors during render: %s", console_errors[:5])
        if blocked_requests:
            logger.info("[renderer] Blocked/unwhitelisted requests: %s", blocked_requests[:5])

        logger.info(
            "[renderer] HTML done: %s (%dx%d, %d bytes, enhanced=%s)",
            local_path, dimensions["width"], dimensions["height"], file_size, use_enhanced,
        )
        return {
            "status": "success",
            "local_path": local_path,
            "width": dimensions["width"],
            "height": dimensions["height"],
        }

    except Exception as e:
        logger.error("[renderer] HTML render failed: %s", e, exc_info=True)
        return {"status": "error", "error": f"HTML render failed: {e}"}

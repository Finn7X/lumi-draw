"""
HTML rendering agent tool.

Renders HTML code to a PNG image and uploads it, returning an accessible URL.
Supports both pure CSS and enhanced_web (ECharts) rendering modes.
"""

import json
import logging

from langchain_core.tools import tool

from ..util.renderer import render_html_to_image
from ..util.uploader import upload_image

logger = logging.getLogger(__name__)


@tool
def generate_html_image(html_code: str, width: int = 1200) -> str:
    """将 HTML 代码渲染为图片。

    适用于：表格、数据展示、复杂排版、仪表盘、卡片、信息图、ECharts 图表等。
    支持纯 CSS 页面和使用 ECharts 库的页面（自动检测渲染模式）。
    中文使用 Microsoft YaHei 字体。

    参数:
        html_code: 完整的 HTML 代码（包含 <!DOCTYPE html> 或 <html> 标签）
        width: 视口宽度（像素），默认 1200

    返回:
        JSON 字符串：包含 status, image_url, local_path, width, height
    """
    try:
        logger.info("[Tool:generate_html_image] Rendering, viewport_width=%d", width)

        render_result = render_html_to_image(html_code, viewport_width=width)
        if render_result["status"] != "success":
            return json.dumps(render_result, ensure_ascii=False)

        local_path = render_result["local_path"]

        upload_result = upload_image(local_path)
        if upload_result["status"] != "success":
            return json.dumps({
                "status": "error",
                "error": upload_result.get("error", "Upload failed"),
                "local_path": local_path,
            }, ensure_ascii=False)

        result = {
            "status": "success",
            "image_url": upload_result["url"],
            "local_path": local_path,
            "width": render_result["width"],
            "height": render_result["height"],
        }

        logger.info(
            "[Tool:generate_html_image] Done: %s (%dx%d)",
            result["image_url"], result["width"], result["height"],
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error("[Tool:generate_html_image] Error: %s", e, exc_info=True)
        return json.dumps({
            "status": "error",
            "error": f"HTML image generation failed: {e}"
        }, ensure_ascii=False)

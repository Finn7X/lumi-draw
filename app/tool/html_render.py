"""
HTML rendering agent tool.

Renders HTML code to a PNG image and uploads it, returning an accessible URL.
Supports both pure CSS and enhanced_web (ECharts) rendering modes.
"""

import json
import logging

from langchain.tools import ToolRuntime
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


@tool
def generate_html_image_from_vfs(
    file_path: str,
    width: int = 1200,
    runtime: ToolRuntime = None,
) -> str:
    """从虚拟文件系统中的 HTML 文件渲染图片。

    适用于长 HTML 或多轮编辑场景：先用 write_file/edit_file 维护 HTML，
    再用本工具按文件路径渲染，避免把整段 HTML 再次放入工具参数。

    参数:
        file_path: 虚拟文件系统中的绝对路径（例如 /workspace/design.html）
        width: 视口宽度（像素），默认 1200

    返回:
        JSON 字符串：包含 status, image_url, local_path, width, height, source_file
    """
    try:
        if runtime is None:
            return json.dumps(
                {"status": "error", "error": "Tool runtime is missing"},
                ensure_ascii=False,
            )

        if not file_path.startswith("/"):
            return json.dumps(
                {"status": "error", "error": "file_path must be an absolute virtual path"},
                ensure_ascii=False,
            )

        files = runtime.state.get("files", {})
        file_data = files.get(file_path)
        if file_data is None:
            return json.dumps(
                {"status": "error", "error": f"Virtual file not found: {file_path}"},
                ensure_ascii=False,
            )

        lines = file_data.get("content", [])
        html_code = "\n".join(lines).strip()
        if not html_code:
            return json.dumps(
                {"status": "error", "error": f"Virtual file is empty: {file_path}"},
                ensure_ascii=False,
            )

        logger.info(
            "[Tool:generate_html_image_from_vfs] Rendering from virtual file=%s, viewport_width=%d",
            file_path, width,
        )

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
            "source_file": file_path,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("[Tool:generate_html_image_from_vfs] Error: %s", e, exc_info=True)
        return json.dumps(
            {"status": "error", "error": f"VFS HTML image generation failed: {e}"},
            ensure_ascii=False,
        )

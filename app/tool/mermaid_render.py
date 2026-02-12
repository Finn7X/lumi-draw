"""
Mermaid rendering agent tool.

Renders Mermaid diagram code to a PNG image and uploads it.
"""

import json
import logging

from langchain_core.tools import tool

from ..util.renderer import render_mermaid_to_image
from ..util.uploader import upload_image

logger = logging.getLogger(__name__)


@tool
def generate_mermaid_image(mermaid_code: str, theme: str = "default") -> str:
    """将 Mermaid 代码渲染为图片。

    适用于：流程图、时序图、甘特图、类图、状态图、ER图、饼图等标准图表。
    使用标准 Mermaid 语法，中文文本直接书写即可。

    参数:
        mermaid_code: Mermaid 图表代码（不含 ```mermaid 标记）
        theme: Mermaid 主题，可选 default/dark/forest/neutral，默认 default

    返回:
        JSON 字符串：包含 status, image_url, local_path, width, height
    """
    try:
        logger.info("[Tool:generate_mermaid_image] Rendering, theme=%s", theme)

        render_result = render_mermaid_to_image(mermaid_code, theme=theme)
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
            "[Tool:generate_mermaid_image] Done: %s (%dx%d)",
            result["image_url"], result["width"], result["height"],
        )
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error("[Tool:generate_mermaid_image] Error: %s", e, exc_info=True)
        return json.dumps({
            "status": "error",
            "error": f"Mermaid image generation failed: {e}"
        }, ensure_ascii=False)

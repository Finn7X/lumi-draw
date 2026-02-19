"""
VL quality check agent tool.

Uses Qwen3-VL-30B vision-language model to evaluate generated images.
Fail-open strategy: defaults to pass when the VL model is unavailable.
"""

import os
import re
import json
import base64
import logging

import httpx
from langchain_core.tools import tool

from ..config import get_settings

logger = logging.getLogger(__name__)


@tool
def check_image_quality(image_path: str, description: str) -> str:
    """对生成的图片进行质量检查。

    使用 VL（视觉语言）模型评估图片质量，判断是否符合用户描述。
    必须在返回图片 URL 给用户之前调用此工具。

    参数:
        image_path: 图片的本地文件路径（由 generate_html_image 返回的 local_path）
        description: 用户的原始图片描述/需求

    返回:
        JSON 字符串：包含 status, passed(bool), score(0-10), assessment, issues[], suggestions[]
    """
    settings = get_settings()

    try:
        if not os.path.exists(image_path):
            return json.dumps({
                "status": "error",
                "error": f"Image file not found: {image_path}"
            }, ensure_ascii=False)

        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        evaluation_prompt = f"""请评估这张图片的质量。用户的需求描述是："{description}"

请从以下维度评分（每项 0-10 分）并给出整体评分：
1. 内容完整性：图片内容是否完整地表达了用户的需求
2. 可读性：文字、标签、数据是否清晰可读
3. 视觉质量：布局是否合理、配色是否协调、整体美观度
4. 准确性：信息展示是否准确、无明显错误

请严格以如下 JSON 格式回复，不要包含任何其他内容：
{{"score": <整体评分0-10>, "assessment": "<整体评价>", "issues": ["<问题1>", "<问题2>"], "suggestions": ["<建议1>", "<建议2>"]}}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_data}"},
                    },
                    {"type": "text", "text": evaluation_prompt},
                ],
            }
        ]

        payload = {
            "model": settings.vl_model_name,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 1024,
        }

        client = httpx.Client(
            verify=False,
            trust_env=False,
            timeout=httpx.Timeout(connect=10.0, read=60.0, write=10.0, pool=5.0),
        )

        headers = {
            "Content-Type": "application/json",
            "Cookie": "Secure"
        }

        response = client.post(settings.vl_model_url, json=payload, headers=headers)
        response.raise_for_status()

        result = response.json()
        content = result["choices"][0]["message"]["content"]

        evaluation = _parse_vl_response(content, settings.vl_quality_threshold)
        passed = evaluation.get("score", 0) >= settings.vl_quality_threshold

        output = {
            "status": "success",
            "passed": passed,
            "score": evaluation.get("score", 0),
            "assessment": evaluation.get("assessment", ""),
            "issues": evaluation.get("issues", []),
            "suggestions": evaluation.get("suggestions", []),
        }

        logger.info("[Tool:check_image_quality] Score: %d/10, passed: %s", output["score"], output["passed"])
        return json.dumps(output, ensure_ascii=False, indent=2)

    except Exception as e:
        # Fail-open: default to pass when VL model is unavailable
        logger.warning("[Tool:check_image_quality] VL model call failed, fail-open: %s", e)
        return json.dumps({
            "status": "success",
            "passed": True,
            "score": 0,
            "assessment": f"VL quality model unavailable ({e}), defaulting to pass",
            "issues": [],
            "suggestions": [],
        }, ensure_ascii=False, indent=2)


def _parse_vl_response(content: str, threshold: int) -> dict:
    """Parse the VL model response and extract the JSON evaluation result."""
    # Direct JSON parse
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # Extract from markdown code block
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?```', content, re.DOTALL)
    if json_match:
        try:
            return json.loads(json_match.group(1))
        except json.JSONDecodeError:
            pass

    # Find JSON object with "score" key
    brace_match = re.search(r'\{[^{}]*"score"[^{}]*\}', content, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    logger.warning("[check_image_quality] Cannot parse VL response: %s", content[:200])
    return {
        "score": threshold,
        "assessment": "VL response format error, defaulting to pass",
        "issues": [],
        "suggestions": [],
    }

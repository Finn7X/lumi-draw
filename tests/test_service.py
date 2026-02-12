"""
Image Generation Service tests.

Usage:
    pytest tests/test_service.py -v
"""

import logging

from app.agent.service import ImageGenAgenticService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

TEST_QUESTIONS = [
    "画一个简单的用户登录流程图",
    "绘制一个电商订单处理流程图，包括下单、支付、发货、收货等环节",
    "生成一个微服务架构图，展示API网关、服务注册中心、多个微服务模块",
    "画一个典型的三层Web应用架构图（前端、后端、数据库）",
    "绘制一个用户购买商品的时序图，包含用户、前端、订单服务、支付服务",
    "生成一个JWT认证流程的时序图",
    "画一个订单状态机图，包含待支付、已支付、已发货、已完成、已取消等状态",
    "绘制一个任务状态流转图，包含待处理、处理中、已完成、已挂起状态",
    "生成一个公司组织架构图，包含CEO、技术部、产品部、市场部等",
    "画一个数据库ER图，展示用户、订单、商品三个实体及其关系",
]


def test_service_initialization():
    """Test that the service can be instantiated."""
    service = ImageGenAgenticService(service_name="test_image_gen")
    assert service.service_name == "test_image_gen"


def test_single_query():
    """Smoke test: run a single query end-to-end."""
    service = ImageGenAgenticService(service_name="test_image_gen")
    result = service.generate_image(
        query=TEST_QUESTIONS[0],
        user_id="test_user_1",
    )
    assert isinstance(result, str)
    assert len(result) > 0
    logger.info("Result (first 500 chars): %s", result[:500])


if __name__ == "__main__":
    test_service_initialization()
    logger.info("Service initialization test passed.")

    logger.info("Running batch test (%d questions) ...", len(TEST_QUESTIONS))
    service = ImageGenAgenticService(service_name="test_image_gen")

    success, fail = 0, 0
    for i, q in enumerate(TEST_QUESTIONS):
        try:
            r = service.generate_image(query=q, user_id=f"test_user_{i + 1}")
            logger.info("[%d/%d] OK: %s", i + 1, len(TEST_QUESTIONS), r[:200])
            success += 1
        except Exception as exc:
            logger.error("[%d/%d] FAIL: %s", i + 1, len(TEST_QUESTIONS), exc)
            fail += 1

    logger.info("Done. success=%d, fail=%d", success, fail)

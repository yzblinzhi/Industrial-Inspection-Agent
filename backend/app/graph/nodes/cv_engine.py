"""CV_Engine 节点：调 CVProvider（Mock/真实 YOLO 同契约），Pydantic 强校验后入 State。
检测单据在此创建——工件号已完成解析与登记校验，杜绝 UNKNOWN 脏单。"""
import logging

from app.providers.factory import get_cv_provider
from app.schemas.cv import CVResult
from app.services import inspection as inspection_service

logger = logging.getLogger(__name__)


async def node(state: dict) -> dict:
    image_key = state.get("image_key")
    if not image_key:
        raise ValueError("CV_Engine 节点缺少 image_key")
    wp = state.get("workpiece_info") or {}
    workpiece_no = wp.get("workpiece_no") or ""

    # 单据先行（按本轮 inspection_uid 独立成单；工件号已过登记校验）
    await inspection_service.ensure_record(
        inspection_uid=state.get("inspection_uid"),
        session_id=state.get("session_id") or "",
        user_id=state.get("user_id") or 0,
        workpiece_no=workpiece_no,
        batch_no=wp.get("batch_no"),
        image_key=image_key,
    )

    raw = await get_cv_provider().detect(image_key, workpiece_no)
    result = CVResult.model_validate(raw)  # 契约校验：不合格直接抛错
    logger.info(
        "CV 完成: %s 检出 %d 处缺陷", workpiece_no or image_key, len(result.detections)
    )
    return {"cv_result": result.model_dump(), "status": "detecting"}

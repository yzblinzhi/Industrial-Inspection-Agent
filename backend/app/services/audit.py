"""审计日志（轻量版）：关键动作落表，异常不阻断主流程。"""
import logging

from app.core.db import SessionLocal
from app.models import AuditLog

logger = logging.getLogger(__name__)


async def write_audit(
    user_id: int | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: dict | None = None,
) -> None:
    try:
        async with SessionLocal() as session:
            session.add(
                AuditLog(
                    user_id=user_id,
                    action=action,
                    target_type=target_type,
                    target_id=str(target_id) if target_id is not None else None,
                    detail=detail or {},
                )
            )
            await session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("审计写入失败（不阻断主流程）: %s", exc)

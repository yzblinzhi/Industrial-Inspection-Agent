"""管理员：审计日志查询（轻量）。"""
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import require_role
from app.core.db import SessionLocal
from app.models import AuditLog, User

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/audit-logs")
async def audit_logs(
    page: int = 1,
    size: int = 50,
    user: User = Depends(require_role("admin")),
):
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(AuditLog)
                .order_by(AuditLog.id.desc())
                .offset((page - 1) * size)
                .limit(size)
            )
        ).scalars().all()
        usernames = {}
        if rows:
            ids = {r.user_id for r in rows if r.user_id}
            users = (
                await session.execute(select(User).where(User.id.in_(ids)))
            ).scalars().all()
            usernames = {u.id: u.username for u in users}
    return [
        {
            "id": r.id,
            "user": usernames.get(r.user_id),
            "action": r.action,
            "target_type": r.target_type,
            "target_id": r.target_id,
            "detail": r.detail,
            "created_at": r.created_at,
        }
        for r in rows
    ]

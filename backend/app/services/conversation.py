"""会话元数据服务：侧栏列表 + 消息计数维护。"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import Conversation

logger = logging.getLogger(__name__)


async def ensure_conversation(session_id: str, user_id: int, title_seed: str) -> None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
        ).scalar_one_or_none()
        if row is None:
            session.add(
                Conversation(
                    session_id=session_id,
                    user_id=user_id,
                    title=(title_seed or "新检测会话")[:60],
                    message_count=0,
                )
            )
        await session.commit()


async def touch(session_id: str, message_count: int | None = None) -> None:
    async with SessionLocal() as session:
        row = (
            await session.execute(
                select(Conversation).where(Conversation.session_id == session_id)
            )
        ).scalar_one_or_none()
        if row is not None:
            row.last_active_at = datetime.now(timezone.utc)
            if message_count is not None:
                row.message_count = message_count
            await session.commit()


async def list_for_user(user_id: int, limit: int = 50) -> list[Conversation]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Conversation)
                .where(Conversation.user_id == user_id)
                .order_by(Conversation.last_active_at.desc())
                .limit(limit)
            )
        ).scalars().all()
        return list(rows)

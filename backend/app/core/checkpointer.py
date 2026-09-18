"""LangGraph Checkpointer：优先 Redis 异步实现（与向量库同库 DB0，前缀隔离），不可用时降级内存版。
注意：langgraph-checkpoint-redis 的同步 RedisSaver 未实现 astream 所需的异步方法，
异步应用必须使用 AsyncRedisSaver（文档 5.5）。"""
import logging

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _acquire_async_redis_saver():
    from langgraph.checkpoint.redis import AsyncRedisSaver

    settings = get_settings()
    ttl_min = max(1, settings.redis_state_ttl_sec // 60)
    try:
        return AsyncRedisSaver(
            redis_url=settings.redis_state_dsn,
            ttl={"default_ttl": ttl_min, "refresh_on_read": True},
        )
    except TypeError:
        return AsyncRedisSaver(redis_url=settings.redis_state_dsn)


async def build_checkpointer():
    """返回已 setup 的 checkpointer；Redis 故障时降级 InMemorySaver（重启后会话丢失）。"""
    try:
        cp = _acquire_async_redis_saver()
        await cp.asetup()
        logger.info("LangGraph checkpointer = AsyncRedisSaver (%s)", get_settings().redis_state_dsn)
        return cp
    except Exception as exc:  # noqa: BLE001 —— 任何 Redis 故障都降级，不阻断启动
        logger.warning("AsyncRedisSaver 不可用(%s)，降级 InMemorySaver", exc)
        from langgraph.checkpoint.memory import InMemorySaver

        return InMemorySaver()

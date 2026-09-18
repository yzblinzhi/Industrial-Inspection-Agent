"""会话列表与消息回放（消息体存于 LangGraph Checkpointer；图片与检测记录关联一并返回）。"""
from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models import User
from app.services import conversation as conversation_service
from app.services import inspection as inspection_service
from app.services import storage

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("")
async def list_conversations(user: User = Depends(get_current_user)):
    rows = await conversation_service.list_for_user(user.id)
    return [
        {
            "session_id": r.session_id,
            "title": r.title,
            "message_count": r.message_count,
            "last_active_at": r.last_active_at,
        }
        for r in rows
    ]


@router.get("/{session_id}/messages")
async def replay_messages(session_id: str, request: Request, user: User = Depends(get_current_user)):
    rows = await conversation_service.list_for_user(user.id, limit=500)
    if user.role != "admin" and all(r.session_id != session_id for r in rows):
        raise HTTPException(404, "会话不存在")

    graph = request.app.state.graph
    snap = await graph.aget_state({"configurable": {"thread_id": session_id}})
    msgs = (snap.values or {}).get("messages") or []

    # 会话内的检测记录：image_key → inspection_id（供前端点击气泡查看详情）
    inspections = await inspection_service.list_by_session(session_id)
    by_image = {i.image_key: i for i in inspections if i.image_key}
    latest = inspections[-1] if inspections else None

    s = get_settings()
    out = []
    for m in msgs:
        item = {"role": "user" if m.type == "human" else "assistant", "content": str(m.content)}
        image_key = (getattr(m, "additional_kwargs", None) or {}).get("image_key")
        if image_key:
            try:
                bucket, _, key = image_key.partition("/")
                item["image"] = storage.presign(bucket, key)
            except Exception:  # noqa: BLE001
                item["image"] = None
            insp = by_image.get(image_key)
            if insp is not None:
                item["inspection_id"] = insp.id
        out.append(item)

    return {
        "session_id": session_id,
        "last_inspection_id": latest.id if latest else None,
        "messages": out,
    }

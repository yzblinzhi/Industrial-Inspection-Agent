"""质检对话流（SSE）。"""
from fastapi import APIRouter, Depends, Request
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user
from app.models import User
from app.schemas.chat import ChatStreamRequest

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/stream")
async def chat_stream(req: ChatStreamRequest, request: Request, user: User = Depends(get_current_user)):
    agent = request.app.state.agent
    return EventSourceResponse(agent.run_stream(req, user))

"""AgentService：LangGraph 流转 ↔ SSE 事件流映射（文档 9.2 协议）。

事件：stage / cv_result / token / status / report / done / error
- token 打字机：最终报告、问答回答、填报指引均按分片推送；
- 检测结论只有 pass / fail 两态；复核走"操作工申请 + 工作台处置"（REST），无图内 interrupt。
"""
import asyncio
import json
import logging
import uuid
from typing import AsyncIterator

from langchain_core.messages import HumanMessage

from app.schemas.chat import ChatStreamRequest
from app.services import audit, conversation, inspection, storage

logger = logging.getLogger(__name__)


def _sse(event: str, data) -> dict:
    return {"event": event, "data": json.dumps(data, ensure_ascii=False, default=str)}


def _chunks(text: str, size: int = 6) -> list[str]:
    return [text[i : i + size] for i in range(0, len(text), size)] if text else []


class AgentService:
    def __init__(self, graph) -> None:
        self.graph = graph

    # ---------------- 公共：图流转 → SSE ----------------
    async def _iter_graph_events(self, graph_input, config: dict) -> AsyncIterator[dict]:
        async for chunk in self.graph.astream(graph_input, config, stream_mode="updates"):
            for node_name, diff in chunk.items():
                if not isinstance(diff, dict):
                    continue
                yield _sse("stage", {"node": node_name, "status": "done"})
                if "cv_result" in diff and diff.get("cv_result"):
                    yield _sse("cv_result", diff["cv_result"])
                if "status" in diff:
                    yield _sse("status", {"status": diff["status"]})
                # 打字机：最终报告（自检已过）、问答回答、填报指引
                if node_name == "report_generator" and diff.get("analysis_report"):
                    summary = diff["analysis_report"].get("summary_text", "")
                    for piece in _chunks(summary):
                        yield _sse("token", {"delta": piece})
                        await asyncio.sleep(0.012)
                    yield _sse("report", diff["analysis_report"])
                if node_name in ("qa_answer", "input_parser") and diff.get("messages"):
                    content = diff["messages"][-1].content
                    for piece in _chunks(str(content)):
                        yield _sse("token", {"delta": piece})
                        await asyncio.sleep(0.012)

    async def _finalize(self, config: dict, session_id: str) -> dict:
        values = (await self.graph.aget_state(config)).values or {}
        msgs = values.get("messages") or []
        try:
            await conversation.touch(session_id, message_count=len(msgs))
        except Exception as exc:  # noqa: BLE001
            logger.warning("会话计数更新失败: %s", exc)
        return {
            "session_id": session_id,
            "status": values.get("status"),
            "inspection_id": values.get("last_inspection_id"),
        }

    # ---------------- 新消息（检测/问答/复核申请） ----------------
    async def run_stream(self, req: ChatStreamRequest, user) -> AsyncIterator[dict]:
        session_id = req.session_id or uuid.uuid4().hex
        try:
            await conversation.ensure_conversation(session_id, user.id, req.message)
        except Exception as exc:  # noqa: BLE001
            yield _sse("error", {"message": f"数据库不可用，请确认容器已启动: {exc}"})
            return

        if req.image_key:
            await audit.write_audit(user.id, "start_inspection", "inspection", session_id)
        else:
            await audit.write_audit(user.id, "chat_message", "conversation", session_id)

        input_state = {
            "session_id": session_id,
            "user_id": user.id,
            "user_role": user.role,
            "user_input": req.message,
            "image_key": req.image_key,
            # 每轮检测独立单据标识（同会话多次检测互不覆盖）
            "inspection_uid": uuid.uuid4().hex if req.image_key else None,
            "image_url": storage.presign(*_split_key(req.image_key)) if req.image_key else None,
            "messages": [
                # image_key 存入 additional_kwargs：随 checkpoint 持久化用于回放，不会进入 LLM 上下文
                HumanMessage(
                    content=req.message,
                    additional_kwargs={"image_key": req.image_key} if req.image_key else {},
                )
            ],
            # 重置跨轮流程字段（上一轮的自检状态不得带入新一轮检测）
            "reflection_retries": 0,
            "reflection_ok": False,
            "reflection_errors": [],
            "validator_notice": None,
        }
        config = {"configurable": {"thread_id": session_id}}
        try:
            async for ev in self._iter_graph_events(input_state, config):
                yield ev
            yield _sse("done", await self._finalize(config, session_id))
        except Exception as exc:  # noqa: BLE001
            logger.exception("agent stream error")
            yield _sse("error", {"message": f"处理失败: {exc}"})


def _split_key(image_key: str) -> tuple[str, str]:
    bucket, _, key = image_key.partition("/")
    return bucket, key

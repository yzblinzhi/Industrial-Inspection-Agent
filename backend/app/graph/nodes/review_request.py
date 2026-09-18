"""Review_Request 节点：操作工在对话中申请复核（"请求复核"/"不认可"等）。
定位本人最近一条相关检测记录 → 标记 need_review 进入复核工作台；不经过图中断。"""
import logging

from langchain_core.messages import AIMessage

from app.services import inspection as inspection_service

logger = logging.getLogger(__name__)


async def node(state: dict) -> dict:
    wp = state.get("workpiece_info") or {}
    text = state.get("user_input") or ""
    insp_id = await inspection_service.request_review(
        user_id=state.get("user_id") or 0,
        role=state.get("user_role", "operator"),
        last_inspection_id=state.get("last_inspection_id"),
        workpiece_no=wp.get("workpiece_no"),
        comment=text,
    )
    if insp_id:
        msg = f"✅ 已提交复核申请（记录 #{insp_id}），工艺员将在复核工作台处理，处理结果可在历史检测记录中查看。"
    else:
        msg = (
            "未找到你的可复核检测记录。请先完成一次检测，"
            "再发送\"申请复核 + 工件号\"（例：`申请复核 CL-ZH02-B`）。"
        )
    return {"messages": [AIMessage(content=msg)]}

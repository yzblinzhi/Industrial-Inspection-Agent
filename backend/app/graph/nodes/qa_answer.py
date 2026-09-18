"""QA_Answer 节点：无图会话的多轮问答 / 历史查询；引用最近检测快照 + 工艺知识，按角色裁剪。"""
import logging

from langchain_core.messages import AIMessage

from app.prompts.qa import build_qa_messages
from app.providers.factory import get_llm_provider, get_rag_provider
from app.schemas.cv import defect_cn
from app.schemas.intent import QaAnswer
from app.services import inspection as inspection_service

logger = logging.getLogger(__name__)


def _fallback_answer(state: dict, docs: list[dict]) -> str:
    parts = []
    if state.get("last_inspection_id"):
        parts.append("已引用你最近一次检测记录。")
    if docs:
        parts.append(f"结合工艺知识《{docs[0].get('title', '')}》：{docs[0].get('text', '')[:150]}……")
    return " ".join(parts) or "暂无可引用的检测记录与工艺知识，请先发起一次检测。"


async def node(state: dict) -> dict:
    question = state.get("user_input") or ""
    role = state.get("user_role", "operator")

    # 1) 最近检测快照（同会话上一轮的检测结果）
    snapshot = None
    if state.get("last_inspection_id"):
        try:
            snapshot = await inspection_service.get_brief(state["last_inspection_id"])
        except Exception as exc:  # noqa: BLE001
            logger.warning("读取检测快照失败: %s", exc)

    # 2) 检索工艺知识：问题文本 + 本会话已检出的缺陷类型
    kws = [g.get("defect_type", "") for g in state.get("standard_gaps") or [] if g.get("defect_type")]
    query = " ".join([question] + kws + [defect_cn(k) for k in kws])
    try:
        docs = await get_rag_provider().retrieve(query, top_k=3)
    except Exception as exc:  # noqa: BLE001
        docs = []
        logger.warning("问答 RAG 检索失败: %s", exc)

    # 3) 角色裁剪：操作工不得获得工艺参数数值
    if role == "operator":
        docs = [{**d, "params": {}} for d in docs]

    facts = {
        "question": question,
        "user_role": role,
        "last_inspection": snapshot,
        "standard_gaps": state.get("standard_gaps") or [],
        "rag_docs": docs,
    }
    try:
        result = await get_llm_provider().chat(
            build_qa_messages(facts, history=state.get("messages", [])), QaAnswer
        )
        answer = result.answer if isinstance(result, QaAnswer) else str(result)
    except Exception as exc:  # noqa: BLE001
        logger.warning("问答 LLM 失败，使用兜底回答: %s", exc)
        answer = _fallback_answer(state, docs)

    return {"messages": [AIMessage(content=answer)]}

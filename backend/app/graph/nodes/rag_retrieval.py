"""RAG_Retrieval 节点：按超标/可疑缺陷类型检索工艺知识，结果带 doc_id 与参数范围。"""
import json
import logging

from app.providers.factory import get_rag_provider
from app.schemas.cv import defect_cn

logger = logging.getLogger(__name__)


def build_query(state: dict) -> str:
    kws = [g.get("defect_type", "") for g in state.get("standard_gaps") or []]
    kws += [s.get("defect_type", "") for s in state.get("suspects") or []]
    if not kws:
        kws = ["general"]
    kws = [k for k in kws if k]
    return " ".join(kws + [defect_cn(k) for k in kws])


async def node(state: dict) -> dict:
    query = build_query(state)
    try:
        docs = await get_rag_provider().retrieve(query, top_k=3)
    except Exception as exc:  # noqa: BLE001
        logger.warning("RAG 检索失败，继续无知识上下文流程: %s", exc)
        docs = []

    context = "\n\n".join(
        f"[{d['doc_id']}] {d['title']}\n{d['text']}\n参数范围: "
        f"{json.dumps(d.get('params', {}), ensure_ascii=False)}"
        for d in docs
    )
    logger.info("RAG 检索: query=%r 命中 %d 篇", query, len(docs))
    return {"rag_docs": docs, "rag_context": context}

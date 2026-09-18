"""LLM Mock（LLM_PROVIDER=mock）：无需密钥即可跑通全链路的确定性实现。
- IntentParse：规则启发式解析（与真实 qwen 行为对齐）
- ReasoningReport：从 Prompt 中的 facts JSON“完美抽取”，保证数值可溯源
- QaAnswer：基于检测快照 + RAG 文本拼装回答
"""
import asyncio
import hashlib
import json
import re
from typing import Type

from langchain_core.messages import AIMessage, BaseMessage
from pydantic import BaseModel

from app.providers.base import LLMProvider
from app.schemas.cv import defect_cn
from app.schemas.intent import IntentParse, QaAnswer
from app.schemas.reports import ReasoningReport, Suggestion

FACTS_JSON_RE = re.compile(r"<facts>(.*?)</facts>", re.DOTALL)
WORKPIECE_NO_RE = re.compile(r"\b([A-Z]{2,4}-[A-Z0-9]{2,8}-[A-Z0-9])\b")
BATCH_RE = re.compile(r"批次[:：\s]*([A-Za-z0-9\-]+)")


def _last_human_text(messages: list[BaseMessage]) -> str:
    for m in reversed(messages):
        if m.type == "human":
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


def _extract_facts(messages: list[BaseMessage]) -> dict:
    for m in reversed(messages):
        content = m.content if isinstance(m.content, str) else str(m.content)
        match = FACTS_JSON_RE.search(content)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    return {}


class MockLLMProvider(LLMProvider):
    async def chat(self, messages: list, structured: Type[BaseModel] | None = None):
        text = _last_human_text(messages)
        if structured is None:
            return AIMessage(content="（Mock LLM）已收到消息：" + text[:50])

        name = structured.__name__
        if name == "IntentParse":
            return structured.model_validate(self._parse_intent(text))
        if name == "ReasoningReport":
            return structured.model_validate(self._build_report(_extract_facts(messages)))
        if name == "QaAnswer":
            return structured.model_validate(self._build_qa(_extract_facts(messages), text))
        raise ValueError(f"MockLLM 未实现的结构化输出: {name}")

    async def stream(self, messages: list):
        text = "（Mock LLM 流式输出）" + _last_human_text(messages)[:80]
        for i in range(0, len(text), 8):
            yield text[i : i + 8]
            await asyncio.sleep(0.02)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        # 确定性伪向量（仅用于 rag_redis 联调，不用于生产语义检索）
        vecs = []
        for t in texts:
            seed = int(hashlib.md5(t.encode()).hexdigest()[:8], 16)
            vec = [((seed >> (i % 28)) & 0xFF) / 255.0 for i in range(1024)]
            vecs.append(vec)
        return vecs

    # ---------- 内部启发式 ----------
    @staticmethod
    def _parse_intent(text: str) -> dict:
        history_kw = ("历史", "之前", "上次", "记录", "查询", "查一下")
        inspect_kw = ("检测", "检查", "质检", "评估", "看一下这个")
        if WORKPIECE_NO_RE.search(text) and any(k in text for k in inspect_kw):
            intent = "new_inspection"
        elif any(k in text for k in history_kw):
            intent = "history_query"
        else:
            intent = "followup_qa"
        wp = WORKPIECE_NO_RE.search(text)
        batch = BATCH_RE.search(text)
        return {
            "intent": intent,
            "workpiece_no": wp.group(1) if wp else None,
            "batch_no": batch.group(1) if batch else None,
        }

    @staticmethod
    def _build_report(facts: dict) -> dict:
        gaps = facts.get("standard_gaps") or []
        rag_docs = facts.get("rag_docs") or []
        conclusion = facts.get("conclusion_hint") or ("fail" if gaps else "pass")

        # 保守判定（无标准/低置信度）：以 validator_notice 为主体生成分析
        if conclusion == "fail" and not gaps:
            notice = facts.get("validator_notice")
            suspects = facts.get("suspects") or []
            if not notice and suspects:
                notice = (
                    f"检出 {len(suspects)} 处低置信度疑似缺陷（低于置信度阈值），无法确认为合格，"
                    "按不合格处理；如不认可可在检测后申请人工复核。"
                )
            return {
                "conclusion": "fail",
                "root_cause": "",
                "suggestions": [],
                "summary_text": f"### ❌ 不合格（保守判定）\n\n{notice or '检出疑似缺陷但无法量化确认，按不合格处理。'}",
            }
        if conclusion == "need_review":
            return {
                "conclusion": "fail",
                "root_cause": "",
                "suggestions": [],
                "summary_text": "### ❌ 不合格（保守判定）\n\n系统无法给出稳定的合格结论，按不合格处理；可在检测后申请人工复核。",
            }

        root_map = {
            "sagging": "涂料黏度偏低 / 喷涂量过大 / 枪距过近，导致湿膜局部过厚垂流",
            "orange_peel": "涂料流平性不足或雾化不良，橘纹未充分展平",
            "color_deviation": "色浆批次差异或膜厚不均，导致色差超标",
            "particle": "环境洁净度不足或涂料未充分过滤，表面混入颗粒",
        }
        suggestions, lines = [], []
        doc = rag_docs[0] if rag_docs else None
        for g in gaps:
            dt = g["defect_type"]
            param = (doc or {}).get("params", {})
            # 取该缺陷工艺文档里第一个范围型参数作为整改建议值
            param_name, rng = next(
                ((k, v) for k, v in param.items() if isinstance(v, list) and len(v) == 2),
                ("工艺参数", None),
            )
            pv = f"{rng[0]:.2f}~{rng[1]:.2f}" if rng else "见工艺规程"
            actual = g.get("actual", {})
            limit = g.get("limit", {})
            ak = next(iter(actual), "value")
            lk = next(iter(limit), ak)
            lines.append(
                f"- **{defect_cn(dt)}**：实测 {actual.get(ak)} {ak}，标准限值 {limit.get(lk)}，"
                f"超标 {g.get('exceed_ratio', 1.0):.2f} 倍"
            )
            suggestions.append(
                Suggestion(
                    defect_type=dt,
                    param_name=param_name,
                    param_value=pv,
                    action=f"按《{(doc or {}).get('title', '工艺规程')}》调整 {param_name} 后复检",
                    source=f"rag_{(doc or {}).get('doc_id', 'manual')}",
                ).model_dump()
            )

        parts = [f"### 检测结论：{'❌ 不合格' if conclusion == 'fail' else '✅ 合格'}\n"]
        parts.append(
            "**超标项：**\n" + "\n".join(lines) + "\n" if lines else "各检测项均在标准限值内。\n"
        )
        if gaps:
            parts.append(
                f"\n**根因分析：** {root_map.get(gaps[0]['defect_type'], '综合工艺因素')}"
                f"（详见《{(doc or {}).get('title', '工艺规程')}》）\n"
            )
        if suggestions:
            parts.append(
                "\n**整改建议：**\n"
                + "\n".join(
                    f"- {s['defect_type']}：调整 {s['param_name']} 至 {s['param_value']}"
                    for s in suggestions
                )
            )
        return {
            "conclusion": conclusion,
            "root_cause": root_map.get(gaps[0]["defect_type"], "") if gaps else "",
            "suggestions": suggestions,
            "summary_text": "\n".join(parts),
        }

    @staticmethod
    def _build_qa(facts: dict, question: str) -> dict:
        snap = facts.get("last_inspection") or {}
        rag_docs = facts.get("rag_docs") or []
        answer = "（Mock LLM）"
        if snap:
            answer += f"你上次检测的工件 {snap.get('workpiece_no')} 结论为「{snap.get('status')}」；"
        if rag_docs:
            answer += f"结合工艺知识《{rag_docs[0]['title']}》：{rag_docs[0]['text'][:120]}……"
        if not snap and not rag_docs:
            answer += "暂无可引用的检测记录与工艺知识，请先发起一次检测。"
        return {"answer": answer}

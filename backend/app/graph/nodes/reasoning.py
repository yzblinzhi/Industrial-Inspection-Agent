"""Reasoning_Agent 节点：LLM 结构化根因分析；失败自动重试，超限降级 need_review（文档 14.1）。"""
import logging

from app.prompts.reasoning import build_reasoning_messages
from app.providers.factory import get_llm_provider
from app.providers.llm_qwen import LLMAuthError
from app.schemas.reports import ReasoningReport

logger = logging.getLogger(__name__)
MAX_RETRY = 2  # 首次失败后再重试 2 次

FALLBACK_REPORT = ReasoningReport(
    conclusion="fail",
    root_cause="分析引擎暂时无法给出稳定结论",
    suggestions=[],
    summary_text=(
        "### ❌ 不合格（保守判定）\n\n分析引擎暂时无法给出稳定的量化结论，"
        "按**不合格**处理；请在检测记录上申请人工复核。"
    ),
)


async def node(state: dict) -> dict:
    status = state.get("status") or "fail"
    facts = {
        "workpiece_no": (state.get("workpiece_info") or {}).get("workpiece_no"),
        "batch_no": (state.get("workpiece_info") or {}).get("batch_no"),
        "cv_result": state.get("cv_result") or {},
        "standard_gaps": state.get("standard_gaps") or [],
        "suspects": state.get("suspects") or [],
        "validator_notice": state.get("validator_notice"),
        "rag_docs": state.get("rag_docs") or [],
        "conclusion_hint": status,
        "reflection_errors": state.get("reflection_errors") or [],
    }
    messages = build_reasoning_messages(facts, history=state.get("messages", [])[-10:])

    llm = get_llm_provider()
    last_err: Exception | None = None
    for attempt in range(1 + MAX_RETRY):
        try:
            report = await llm.chat(messages, ReasoningReport)
            if not isinstance(report, ReasoningReport):
                report = ReasoningReport.model_validate(report)
            logger.info("推理完成: conclusion=%s suggestions=%d", report.conclusion, len(report.suggestions))
            return {"analysis_report": report.model_dump()}
        except LLMAuthError:
            raise  # 鉴权失败必须让用户看到，静默降级会掩盖配置错误
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            logger.warning("推理第 %d 次失败: %s", attempt + 1, exc)

    logger.error("推理连续失败，按不合格保守判定: %s", last_err)
    return {
        "analysis_report": FALLBACK_REPORT.model_dump(),
        "status": "fail",
    }

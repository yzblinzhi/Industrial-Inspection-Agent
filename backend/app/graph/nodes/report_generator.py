"""Report_Generator 节点：统一产出 展示文本 + Markdown 归档（MinIO）+ PG 落库（文档 5.2 节点 7）。"""
import logging
from datetime import datetime

from langchain_core.messages import AIMessage

from app.core.config import get_settings
from app.schemas.cv import defect_cn
from app.services import inspection as inspection_service
from app.services import storage

logger = logging.getLogger(__name__)


def render_report_markdown(state: dict, analysis: dict) -> str:
    wp = state.get("workpiece_info") or {}
    cv = state.get("cv_result") or {}
    lines = [
        "# 喷涂工件质检报告",
        "",
        f"- 报告编号/会话：`{state.get('session_id')}`",
        f"- 工件型号：{wp.get('workpiece_no', '-')}（{wp.get('name', '-')}）",
        f"- 批次号：{wp.get('batch_no') or '-'}",
        f"- 检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 判定结论：**{analysis.get('conclusion', state.get('status'))}**",
        "",
        "## 一、缺陷检测结果",
    ]
    detections = cv.get("detections", [])
    if detections:
        lines.append("| # | 缺陷类型 | 置信度 | 面积(cm²) | 最大长度(mm) | ΔE |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for d in detections:
            m = d.get("measure") or {}
            lines.append(
                f"| {d.get('id')} | {defect_cn(d.get('defect_type',''))} "
                f"| {d.get('confidence')} | {m.get('area_cm2', '-')} "
                f"| {m.get('max_length_mm', '-')} | {m.get('delta_e', '-')} |"
            )
    else:
        lines.append("未检出缺陷。")

    lines += ["", "## 二、标准比对（超标项）"]
    gaps = state.get("standard_gaps") or []
    if gaps:
        for g in gaps:
            lines.append(
                f"- {defect_cn(g.get('defect_type', ''))}：实测 {g.get('actual')}，"
                f"限值 {g.get('limit')}，超标 {g.get('exceed_ratio')} 倍"
            )
    else:
        lines.append("各检测项均在标准限值内。")

    lines += ["", "## 三、根因分析", analysis.get("root_cause") or "（无）", "",
              "## 四、整改建议"]
    suggs = analysis.get("suggestions") or []
    if suggs:
        for s in suggs:
            lines.append(
                f"- 【{defect_cn(s.get('defect_type', ''))}】调整 {s.get('param_name')} "
                f"至 {s.get('param_value')}——{s.get('action')}（来源: {s.get('source')}）"
            )
    else:
        lines.append("（无）")
    lines += ["", "## 五、自检记录"]
    errs = state.get("reflection_errors") or []
    lines.append(f"- 自检重试次数：{state.get('reflection_retries', 0)}")
    lines.append(f"- 最后一次自检错误：{'; '.join(errs) if errs else '无'}")
    return "\n".join(lines)


async def node(state: dict) -> dict:
    s = get_settings()
    session_id = state.get("session_id") or ""
    status = state.get("status") or "fail"

    # 保守判定直达路径补齐最小报告结构（notice 只进正文一次）
    analysis = state.get("analysis_report")
    if not analysis:
        if status == "pass":
            analysis = {
                "conclusion": "pass", "root_cause": "", "suggestions": [],
                "summary_text": "### 检测结论：✅ 合格\n\n各检测项均在标准限值内。",
            }
        else:
            body = state.get("validator_notice") or (
                "系统无法给出稳定的合格结论，按不合格处理；可在检测记录上申请人工复核。"
            )
            analysis = {
                "conclusion": "fail", "root_cause": "", "suggestions": [],
                "summary_text": f"### ❌ 不合格（保守判定）\n\n{body}",
            }
    # 自检连续失败被强制判不合格时，纠正与 LLM 文本矛盾的结论标记
    if (
        status == "fail"
        and state.get("reflection_errors")
        and analysis.get("conclusion") == "pass"
    ):
        analysis = {**analysis, "conclusion": "fail"}

    # 1) 报告归档 MinIO（失败不阻断主流程）
    report_key = None
    try:
        report_key = f"{session_id}/report.md"
        await storage.upload_text(s.minio_report_bucket, report_key, render_report_markdown(state, analysis))
        logger.info("报告已归档: %s/%s", s.minio_report_bucket, report_key)
    except Exception as exc:  # noqa: BLE001
        logger.warning("报告归档失败（MinIO 不可用？），继续流程: %s", exc)
        report_key = None

    # 2) 落库（按本轮 inspection_uid 独立单据 upsert，写终态）
    wp = state.get("workpiece_info") or {}
    try:
        insp_id = await inspection_service.save_result(
            inspection_uid=state.get("inspection_uid"),
            session_id=session_id,
            workpiece_no=wp.get("workpiece_no") or "UNKNOWN",
            batch_no=wp.get("batch_no"),
            image_key=state.get("image_key"),
            cv_result=state.get("cv_result"),
            standard_gaps=state.get("standard_gaps") or [],
            analysis_report=analysis,
            status=status,
            report_file_key=report_key,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("检测记录落库失败: %s", exc)
        insp_id = state.get("last_inspection_id")

    # 3) 前端展示消息（notice 若已含在报告正文中则不重复拼接，避免回放后内容"变多"）
    display = analysis.get("summary_text") or ""
    notice = state.get("validator_notice")
    if notice and notice not in display:
        display += f"\n\n> ⚠️ {notice}"
    if not state.get("rag_docs"):
        display += "\n\n> ℹ️ 本次分析未参考 RAG 工艺知识库（未检索到相关知识），请谨慎参考。"
    if state.get("reflection_errors"):
        display += "\n\n> ⚠️ 自检提示：报告曾未通过量化溯源校验并已重新生成；若仍有疑问请联系工艺员复核。"

    return {
        "analysis_report": analysis,
        "report_file_key": report_key,
        "status": status,
        "messages": [AIMessage(content=display)],
        "last_inspection_id": insp_id,
    }

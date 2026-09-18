"""Self_Reflection 节点：硬规则防幻觉校验（必过）+ 重试回流（文档 5.2 硬规则清单）。

5 条硬规则全部可程序化判定、可离线单测：
  R1 结论一致性：gaps 非空 ⟺ conclusion=fail
  R2 缺陷对应：建议中的缺陷类型 ⊆ 超标项类型集合
  R3 参数溯源：建议参数值须落在 RAG 参数范围表内，或与工艺文档正文标注的参数值一致
  R4 数值溯源：结论文本中的所有数值须能在 CV/标准/RAG 数据中找到来源（5% 容差）
  R5 禁用模糊词：根因中禁止"可能/大概/应该是/或许"
"""
import logging
import re

logger = logging.getLogger(__name__)
MAX_RETRY = 2
HEDGE_WORDS = ("可能", "大概", "应该是", "或许")
NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def _numbers_in(text: str) -> list[float]:
    if not text:
        return []
    return [float(x) for x in NUM_RE.findall(str(text))]


def _traceable_numbers(
    standard_gaps: list[dict],
    rag_docs: list[dict],
    cv_result: dict,
    workpiece_info: dict | None = None,
    suspects: list[dict] | None = None,
) -> set[float]:
    nums: set[float] = set()
    cv = cv_result or {}
    dets = cv.get("detections", [])

    # 数量类：检出总数、各类型数量、超标项数、可疑项数
    nums.add(float(len(dets)))
    type_counts: dict[str, int] = {}
    for det in dets:
        dt = det.get("defect_type", "")
        type_counts[dt] = type_counts.get(dt, 0) + 1
    nums.update(float(c) for c in type_counts.values())
    nums.add(float(len(standard_gaps or [])))
    nums.add(float(len(suspects or [])))
    for s in suspects or []:
        for key in ("confidence", "threshold"):
            try:
                nums.add(float(s.get(key, 0)))
            except (TypeError, ValueError):
                pass

    for det in dets:
        nums.add(float(det.get("confidence", 0)))
        for v in (det.get("measure") or {}).values():
            if v is not None:
                try:
                    nums.add(float(v))
                except (TypeError, ValueError):
                    pass
    for g in standard_gaps or []:
        for d in (g.get("actual") or {}, g.get("limit") or {}):
            for v in d.values():
                try:
                    nums.add(float(v))
                except (TypeError, ValueError):
                    pass
        try:
            nums.add(float(g.get("exceed_ratio", 0)))
        except (TypeError, ValueError):
            pass
    for d in rag_docs or []:
        for v in (d.get("params") or {}).values():
            if isinstance(v, list) and len(v) == 2:
                try:
                    nums.update({float(v[0]), float(v[1])})
                except (TypeError, ValueError):
                    pass
        nums.update(_numbers_in(d.get("text", "")))

    # CV 元数据：模型名（yolov8s-spray-v1）、图像尺寸、meta 中的数字（如场景号 S2）
    nums.update(_numbers_in(str(cv.get("model", ""))))
    for v in (cv.get("image_size") or {}).values():
        try:
            nums.add(float(v))
        except (TypeError, ValueError):
            pass
    for v in (cv.get("meta") or {}).values():
        nums.update(_numbers_in(str(v)))

    # 工件号/批次号中的数字（如 B2026-09-01）
    for v in (workpiece_info or {}).values():
        if v:
            nums.update(_numbers_in(str(v)))
    return nums


def run_hard_rules(
    report: dict,
    standard_gaps: list[dict],
    rag_docs: list[dict],
    cv_result: dict,
    workpiece_info: dict | None = None,
    suspects: list[dict] | None = None,
) -> list[str]:
    violations: list[str] = []
    conclusion = report.get("conclusion")
    gaps = standard_gaps or []
    has_findings = bool(gaps or suspects)  # 超标项或低置信度可疑项都可作为不合格依据

    # R1 结论一致性
    if conclusion == "fail" and not has_findings:
        violations.append("R1: 结论为 fail 但不存在超标项或可疑项")
    if conclusion == "pass" and has_findings:
        violations.append("R1: 结论为 pass 但存在超标项或可疑项")

    # R2 缺陷对应
    gap_types = {g.get("defect_type") for g in gaps}
    for s in report.get("suggestions", []) or []:
        if s.get("defect_type") not in gap_types:
            violations.append(f"R2: 建议引用了未检出的缺陷类型 {s.get('defect_type')}")

    # R3 参数溯源：数值落在 params 范围表内，或与工艺文档正文标注的参数值一致（均可溯源）
    ranges: list[tuple[float, float]] = []
    rag_text_nums: set[float] = set()
    for d in rag_docs or []:
        for v in (d.get("params") or {}).values():
            if isinstance(v, list) and len(v) == 2:
                try:
                    ranges.append((float(v[0]), float(v[1])))
                except (TypeError, ValueError):
                    pass
        rag_text_nums.update(_numbers_in(d.get("text", "")))
    for s in report.get("suggestions", []) or []:
        for num in _numbers_in(s.get("param_value", "")):
            in_range = any(lo - 1e-9 <= num <= hi + 1e-9 for lo, hi in ranges)
            in_doc = any(abs(num - a) <= max(abs(a) * 0.05, 1e-6) for a in rag_text_nums)
            if ranges and not (in_range or in_doc):
                violations.append(f"R3: 建议参数 {num} 不在工艺知识参数范围内")

    # R4 数值溯源（5% 相对容差；落在 RAG 参数区间内的数值视为可溯源）
    allowed = _traceable_numbers(standard_gaps, rag_docs, cv_result, workpiece_info, suspects)
    text = f"{report.get('summary_text', '')} {report.get('root_cause', '')}"
    for num in _numbers_in(text):
        traceable = any(abs(num - a) <= max(abs(a) * 0.05, 1e-6) for a in allowed)
        if not traceable and ranges:
            traceable = any(lo - 1e-9 <= num <= hi + 1e-9 for lo, hi in ranges)
        if allowed and not traceable:
            violations.append(f"R4: 结论文本中的数值 {num} 无法溯源到检测/标准/工艺数据")

    # R5 禁用模糊词
    root_cause = report.get("root_cause") or ""
    if any(w in root_cause for w in HEDGE_WORDS):
        violations.append("R5: 根因分析含模糊限定词")

    return violations


async def node(state: dict) -> dict:
    report = state.get("analysis_report") or {}
    violations = run_hard_rules(
        report,
        state.get("standard_gaps") or [],
        state.get("rag_docs") or [],
        state.get("cv_result") or {},
        state.get("workpiece_info") or {},
        state.get("suspects") or [],
    )
    retries = state.get("reflection_retries") or 0

    if not violations:
        return {"reflection_ok": True, "reflection_errors": [], "reflection_retries": retries}

    retries += 1
    if retries > MAX_RETRY:
        # 自检连续失败：结论只有合格/不合格两态，保守判不合格并在报告中展示自检错误
        logger.error("自检连续 %d 次失败，按不合格保守判定: %s", retries, violations)
        return {
            "reflection_ok": False,
            "reflection_retries": retries,
            "reflection_errors": violations,
            "status": "fail",
        }
    logger.warning("自检第 %d 次失败，回流 reasoning 重生成: %s", retries, violations)
    return {
        "reflection_ok": False,
        "reflection_retries": retries,
        "reflection_errors": violations,
    }

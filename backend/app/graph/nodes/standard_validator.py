"""Standard_Validator 节点：PG 结构化阈值 × CV 量化值比对，输出超标项与可疑项。"""
import logging

from app.services.standards import compute_gaps, get_standards

logger = logging.getLogger(__name__)


async def node(state: dict) -> dict:
    workpiece_no = (state.get("workpiece_info") or {}).get("workpiece_no") or ""
    standards = await get_standards(workpiece_no)
    cv = state.get("cv_result") or {}
    gaps, suspects = compute_gaps(cv, standards)

    notice = None
    detections = cv.get("detections", [])
    if not standards and detections:
        # 检出缺陷但无结构化标准可依：检测结论只有合格/不合格两态，按不合格处理
        status = "fail"
        notice = (
            f"工件 `{workpiece_no or '(未提供工件号)'}` 未登记或未配置结构化质检标准"
            f"（检出 {len(detections)} 处疑似缺陷），**按不合格处理**；请核对工件号，"
            "确认无误可在检测后申请人工复核。"
        )
        logger.warning("无标准可判: workpiece=%s detections=%d", workpiece_no or "<空>", len(detections))
    elif gaps:
        status = "fail"
    elif suspects:
        status = "fail"
        notice = (
            f"检出 {len(suspects)} 处低置信度疑似缺陷（低于置信度阈值），无法确认为合格，"
            "**按不合格处理**；如不认可可在检测后申请人工复核。"
        )
    else:
        status = "pass"

    logger.info("标准比对: gaps=%d suspects=%d status=%s", len(gaps), len(suspects), status)
    return {"standard_gaps": gaps, "suspects": suspects, "status": status, "validator_notice": notice}

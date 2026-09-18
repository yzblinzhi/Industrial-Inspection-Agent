"""质检标准服务：读取结构化阈值 + 纯函数比对（可单测，文档 5.2 / 7.1）。"""
import logging

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import QualityStandard, Workpiece

logger = logging.getLogger(__name__)


async def get_standards(workpiece_no: str) -> list[dict]:
    """读取某工件的全部结构化标准（一行 = 一个缺陷类型的合格判据）。"""
    if not workpiece_no:
        return []
    async with SessionLocal() as session:
        stmt = (
            select(Workpiece, QualityStandard)
            .join(QualityStandard, QualityStandard.workpiece_id == Workpiece.id)
            .where(Workpiece.workpiece_no == workpiece_no)
        )
        rows = (await session.execute(stmt)).all()
        return [
            {
                "standard_id": std.id,
                "workpiece_id": wp.id,
                "workpiece_name": wp.name,
                "defect_type": std.defect_type,
                "max_area_cm2": float(std.max_area_cm2) if std.max_area_cm2 is not None else None,
                "max_count": std.max_count,
                "max_dimension_mm": float(std.max_dimension_mm)
                if std.max_dimension_mm is not None
                else None,
                "confidence_threshold": float(std.confidence_threshold)
                if std.confidence_threshold is not None
                else None,
                "extra_rules": std.extra_rules or {},
            }
            for wp, std in rows
        ]


async def list_all_workpieces() -> list[dict]:
    """全部已登记工件（供名称匹配与笔误纠错）。"""
    async with SessionLocal() as session:
        rows = (await session.execute(select(Workpiece))).scalars().all()
        return [
            {"id": w.id, "workpiece_no": w.workpiece_no, "name": w.name}
            for w in rows
        ]


async def get_workpiece(workpiece_no: str) -> dict | None:
    if not workpiece_no:
        return None
    async with SessionLocal() as session:
        row = await session.execute(
            select(Workpiece).where(Workpiece.workpiece_no == workpiece_no)
        )
        wp = row.scalar_one_or_none()
        if wp is None:
            return None
        return {
            "id": wp.id,
            "workpiece_no": wp.workpiece_no,
            "name": wp.name,
            "material": wp.material,
            "coating_spec": wp.coating_spec,
        }


def compute_gaps(
    cv_result: dict, standards: list[dict], default_confidence: float = 0.5
) -> tuple[list[dict], list[dict]]:
    """纯函数：CV 结果 × 结构化标准 → (超标项 gaps, 低置信度可疑项 suspects)。

    - 置信度低于阈值的检出不计入判定，只进 suspects；
    - 单件检出：area_cm2 / max_length_mm / delta_e(色差) 与阈值逐一比对；
    - 数量型判据：同类型检出数超过 max_count 记一条 count 类 gap。
    """
    standards_map = {s["defect_type"]: s for s in standards}
    detections = (cv_result or {}).get("detections", [])
    gaps: list[dict] = []
    suspects: list[dict] = []
    type_counts: dict[str, int] = {}

    for det in detections:
        dt = det.get("defect_type", "")
        std = standards_map.get(dt)
        conf = float(det.get("confidence", 1.0))
        conf_threshold = (std or {}).get("confidence_threshold") or default_confidence
        if conf < conf_threshold:
            suspects.append(
                {
                    "detection_id": det.get("id"),
                    "defect_type": dt,
                    "confidence": conf,
                    "threshold": conf_threshold,
                }
            )
            continue
        type_counts[dt] = type_counts.get(dt, 0) + 1
        if std is None:
            continue  # 无标准的缺陷类型无法量化判定
        measure = det.get("measure") or {}
        actual: dict = {}
        limit: dict = {}
        # measure 字段 ↔ 标准字段映射：area_cm2↔max_area_cm2, max_length_mm↔max_dimension_mm
        if measure.get("area_cm2") is not None and std.get("max_area_cm2") is not None:
            actual["area_cm2"] = float(measure["area_cm2"])
            limit["area_cm2"] = float(std["max_area_cm2"])
        if measure.get("max_length_mm") is not None and std.get("max_dimension_mm") is not None:
            actual["max_length_mm"] = float(measure["max_length_mm"])
            limit["max_length_mm"] = float(std["max_dimension_mm"])
        max_de = (std.get("extra_rules") or {}).get("max_delta_e")
        if measure.get("delta_e") is not None and max_de is not None:
            actual["delta_e"] = float(measure["delta_e"])
            limit["delta_e"] = float(max_de)
        if not actual:
            continue
        exceed = max(actual[k] / limit[k] for k in actual if limit[k] > 0)
        if exceed > 1.0:
            gaps.append(
                {
                    "detection_id": det.get("id"),
                    "defect_type": dt,
                    "actual": actual,
                    "limit": limit,
                    "exceed_ratio": round(exceed, 2),
                    "gap_kind": "measure",
                }
            )

    for dt, cnt in type_counts.items():
        std = standards_map.get(dt)
        if std and std.get("max_count") is not None and cnt > int(std["max_count"]):
            gaps.append(
                {
                    "detection_id": None,
                    "defect_type": dt,
                    "actual": {"count": cnt},
                    "limit": {"max_count": int(std["max_count"])},
                    "exceed_ratio": round(cnt / int(std["max_count"]), 2),
                    "gap_kind": "count",
                }
            )

    return gaps, suspects

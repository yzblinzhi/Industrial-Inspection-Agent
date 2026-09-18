"""检测记录服务：单据先行（pending 落库）→ 各节点推进 → 终态更新（文档 14.3）。"""
import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, text

from app.core.db import SessionLocal
from app.models import InspectionLog, Workpiece

logger = logging.getLogger(__name__)


async def database_view(
    user_id: int,
    role: str,
    workpiece_no: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[dict], int]:
    """检测数据库（去重视图）：按 (工件号, 批次号[空=未分批]) 去重，
    每组取最新一次检测（latest-wins）并统计检测次数。全局可见（操作工字段裁剪在端点层）。"""
    async with SessionLocal() as session:
        conditions: list[str] = []
        params: dict = {}
        if workpiece_no:
            conditions.append("latest.workpiece_no = :wp")
            params["wp"] = workpiece_no
        if status:
            conditions.append("latest.status = :st")
            params["st"] = status
        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        # 分组计数（不去重的总数，用于分页 total）
        count_sql = text(f"""
            SELECT COUNT(*) FROM (
                SELECT i.workpiece_no, COALESCE(i.batch_no, '') AS bkey
                FROM inspection_logs i
                GROUP BY i.workpiece_no, COALESCE(i.batch_no, '')
            ) g
        """)
        total = (await session.execute(count_sql)).scalar_one()

        # DISTINCT ON 取每组最新 + 次数 + 工件名
        rows_sql = text(f"""
            SELECT latest.id, latest.workpiece_no, latest.batch_no,
                   latest.status, latest.created_at, latest.cv_result,
                   latest.analysis_report, latest.image_key,
                   w.name AS workpiece_name, g.check_count
            FROM (
                SELECT DISTINCT ON (i.workpiece_no, COALESCE(i.batch_no, ''))
                       i.*
                FROM inspection_logs i
                ORDER BY i.workpiece_no, COALESCE(i.batch_no, ''), i.id DESC
            ) latest
            JOIN (
                SELECT workpiece_no, COALESCE(batch_no, '') AS bkey,
                       COUNT(*) AS check_count
                FROM inspection_logs
                GROUP BY workpiece_no, COALESCE(batch_no, '')
            ) g ON g.workpiece_no = latest.workpiece_no
               AND g.bkey = COALESCE(latest.batch_no, '')
            LEFT JOIN workpieces w ON w.workpiece_no = latest.workpiece_no
            {where}
            ORDER BY latest.id DESC
            LIMIT :limit OFFSET :offset
        """)
        params.update({"limit": size, "offset": (page - 1) * size})
        result = (await session.execute(rows_sql, params)).mappings().all()

        items = [
            {
                "inspection_id": r["id"],
                "workpiece_no": r["workpiece_no"],
                "workpiece_name": r["workpiece_name"] or "-",
                "batch_no": r["batch_no"],  # 前端空值显示"未分批"
                "check_count": int(r["check_count"]),
                "status": r["status"],
                "created_at": r["created_at"],
                # 详情弹窗数据（操作工裁剪由端点按角色删除）
                "cv_result": r["cv_result"],
                "analysis_report": r["analysis_report"],
                "image_key": r["image_key"],
            }
            for r in result
        ]
        return items, int(total)


async def ensure_record(
    inspection_uid: str | None,
    session_id: str,
    user_id: int,
    workpiece_no: str,
    batch_no: str | None,
    image_key: str | None,
) -> int:
    """检测开始时先落一条 pending 单据（按 inspection_uid 独立成单；崩溃也有单可查）。"""
    async with SessionLocal() as session:
        stmt = select(InspectionLog)
        if inspection_uid:
            stmt = stmt.where(InspectionLog.inspection_uid == inspection_uid)
        else:  # 兼容无 uid 的调用（评测脚本直驱图）
            stmt = stmt.where(InspectionLog.session_id == session_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            wp_id = (
                await session.execute(
                    select(Workpiece.id).where(Workpiece.workpiece_no == workpiece_no)
                )
            ).scalar_one_or_none()
            row = InspectionLog(
                session_id=session_id,
                inspection_uid=inspection_uid,
                workpiece_id=wp_id,
                workpiece_no=workpiece_no or "UNKNOWN",
                batch_no=batch_no,
                image_key=image_key,
                status="pending",
                created_by=user_id,
            )
            session.add(row)
            await session.commit()
            await session.refresh(row)
        return int(row.id)


async def save_result(
    inspection_uid: str | None,
    session_id: str,
    workpiece_no: str,
    batch_no: str | None,
    image_key: str | None,
    cv_result: dict | None,
    standard_gaps: list | None,
    analysis_report: dict | None,
    status: str,
    report_file_key: str | None,
) -> int:
    async with SessionLocal() as session:
        stmt = select(InspectionLog)
        if inspection_uid:
            stmt = stmt.where(InspectionLog.inspection_uid == inspection_uid)
        else:
            stmt = stmt.where(InspectionLog.session_id == session_id)
        row = (await session.execute(stmt)).scalar_one_or_none()
        if row is None:
            wp_id = (
                await session.execute(
                    select(Workpiece.id).where(Workpiece.workpiece_no == workpiece_no)
                )
            ).scalar_one_or_none()
            row = InspectionLog(
                session_id=session_id,
                inspection_uid=inspection_uid,
                workpiece_id=wp_id,
                workpiece_no=workpiece_no or "UNKNOWN",
                batch_no=batch_no,
                image_key=image_key,
                status="pending",
            )
            session.add(row)
        else:
            # 单据先行时工件号尚未解析，此处回填真实值
            if workpiece_no and workpiece_no != "UNKNOWN":
                row.workpiece_no = workpiece_no
                if row.workpiece_id is None:
                    row.workpiece_id = (
                        await session.execute(
                            select(Workpiece.id).where(Workpiece.workpiece_no == workpiece_no)
                        )
                    ).scalar_one_or_none()
            if batch_no:
                row.batch_no = batch_no
        row.cv_result = cv_result
        row.standard_gaps = standard_gaps
        row.analysis_report = analysis_report
        row.status = status
        row.report_file_key = None if report_file_key is None else report_file_key
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(row)
        return int(row.id)


async def get_by_id(inspection_id: int) -> InspectionLog | None:
    async with SessionLocal() as session:
        row = await session.get(InspectionLog, inspection_id)
        return row


async def get_brief(inspection_id: int) -> dict | None:
    row = await get_by_id(inspection_id)
    if row is None:
        return None
    return {
        "id": row.id,
        "workpiece_no": row.workpiece_no,
        "batch_no": row.batch_no,
        "status": row.status,
        "created_at": str(row.created_at),
    }


async def list_by_session(session_id: str) -> list[InspectionLog]:
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(InspectionLog)
                .where(InspectionLog.session_id == session_id)
                .order_by(InspectionLog.id.asc())
            )
        ).scalars().all()
        return list(rows)


async def list_logs(
    user_id: int, role: str, workpiece_no: str | None, batch_no: str | None,
    status: str | None, page: int = 1, size: int = 20, reviewed: bool | None = None,
    session_id: str | None = None,
) -> tuple[list[InspectionLog], int]:
    async with SessionLocal() as session:
        stmt = select(InspectionLog)
        if role == "operator":
            stmt = stmt.where(InspectionLog.created_by == user_id)  # 操作工仅看本人
        if session_id:
            stmt = stmt.where(InspectionLog.session_id == session_id)
        if workpiece_no:
            stmt = stmt.where(InspectionLog.workpiece_no == workpiece_no)
        if batch_no:
            stmt = stmt.where(InspectionLog.batch_no == batch_no)
        if status:
            stmt = stmt.where(InspectionLog.status == status)
        if reviewed is True:
            stmt = stmt.where(InspectionLog.reviewed_by.isnot(None))
        elif reviewed is False:
            stmt = stmt.where(InspectionLog.reviewed_by.is_(None))
            if not status:
                stmt = stmt.where(InspectionLog.status == "need_review")
        total = (
            await session.execute(select(func.count()).select_from(stmt.subquery()))
        ).scalar_one()
        rows = (
            await session.execute(
                stmt.order_by(InspectionLog.id.desc()).offset((page - 1) * size).limit(size)
            )
        ).scalars().all()
        return list(rows), int(total)


async def request_review(
    user_id: int, role: str, last_inspection_id: int | None,
    workpiece_no: str | None, comment: str,
) -> int | None:
    """操作工对本人检测记录发起复核申请：置为 need_review 进入复核工作台。"""
    async with SessionLocal() as session:
        row: InspectionLog | None = None
        if last_inspection_id:
            row = await session.get(InspectionLog, last_inspection_id)
            if row is not None and role == "operator" and row.created_by != user_id:
                row = None
        if row is None and workpiece_no:
            stmt = select(InspectionLog).where(InspectionLog.workpiece_no == workpiece_no)
            if role == "operator":
                stmt = stmt.where(InspectionLog.created_by == user_id)
            row = (
                await session.execute(stmt.order_by(InspectionLog.id.desc()).limit(1))
            ).scalar_one_or_none()
        if row is None:
            return None
        if row.status == "need_review":
            return int(row.id)  # 已在复核队列，幂等
        row.status = "need_review"
        row.review_comment = f"[操作工申请复核] {comment[:200]}".strip()
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return int(row.id)


async def mark_need_review(inspection_id: int, user_id: int, comment: str) -> None:
    """将已出结论的检测记录标记为 need_review（操作工申请复核入口）。"""
    async with SessionLocal() as session:
        row = await session.get(InspectionLog, inspection_id)
        if row is None:
            return
        row.status = "need_review"
        row.review_comment = f"[操作工申请复核] {comment[:200]}".strip()
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()


async def apply_review_direct(
    inspection_id: int, reviewer_id: int, decision: str, comment: str
) -> str | None:
    """复核工作台处置（无需图内 interrupt，直改单据）：
    confirm → fail；reject → rechecking（驳回重检）；revalidate → 按当前标准重判。"""
    from app.services.standards import compute_gaps, get_standards

    async with SessionLocal() as session:
        row = await session.get(InspectionLog, inspection_id)
        if row is None:
            return None
        if decision == "confirm":
            status = "fail"
        elif decision == "reject":
            status = "rechecking"
        else:  # revalidate：用当前最新标准对既有 CV 结果重判
            standards = await get_standards(row.workpiece_no)
            gaps, suspects = compute_gaps(row.cv_result or {}, standards)
            status = "fail" if (gaps or suspects) else "pass"
            row.standard_gaps = gaps
        row.status = status
        row.reviewed_by = reviewer_id
        row.reviewed_at = datetime.now(timezone.utc)
        row.review_comment = f"[{decision}] {comment}".strip()
        row.updated_at = datetime.now(timezone.utc)
        await session.commit()
        return status


async def apply_review(inspection_id: int, reviewer_id: int, decision: str, comment: str) -> None:
    async with SessionLocal() as session:
        row = await session.get(InspectionLog, inspection_id)
        if row is None:
            return
        row.reviewed_by = reviewer_id
        row.reviewed_at = datetime.now(timezone.utc)
        row.review_comment = f"[{decision}] {comment}".strip()
        await session.commit()


def to_out(row: InspectionLog, role: str, image_url: str | None, report_url: str | None) -> dict[str, Any]:
    """按角色裁剪字段（权限在后端，文档 9.3）。"""
    report = row.analysis_report or {}
    if role == "operator":
        conclusion_text = {
            "pass": "✅ 合格",
            "fail": "❌ 不合格，请联系工艺员处理",
            "need_review": "⚠️ 待人工复核",
        }.get(row.status, row.status)
        return {
            "id": row.id,
            "session_id": row.session_id,
            "workpiece_no": row.workpiece_no,
            "batch_no": row.batch_no,
            "status": row.status,
            "conclusion_text": conclusion_text,
            "annotated_image_url": image_url,
            "created_at": row.created_at,
            "review_comment": None if role == "operator" and not row.review_comment else row.review_comment,
        }
    return {
        "id": row.id,
        "session_id": row.session_id,
        "workpiece_id": row.workpiece_id,
        "workpiece_no": row.workpiece_no,
        "batch_no": row.batch_no,
        "status": row.status,
        "conclusion_text": report.get("summary_text", ""),
        "image_key": row.image_key,
        "image_url": image_url,
        "annotated_image_url": image_url,
        "cv_result": row.cv_result,
        "standard_gaps": row.standard_gaps,
        "analysis_report": report,
        "report_file_key": row.report_file_key,
        "report_url": report_url,
        "reviewed_by": row.reviewed_by,
        "reviewed_at": row.reviewed_at,
        "review_comment": row.review_comment,
        "created_at": row.created_at,
    }

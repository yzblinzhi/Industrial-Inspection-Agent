"""复核工单服务：五态流转（pending/done/rejected/reapply/special）。
规则要点：
- 处理人处置 reapply（驳回重审）工单时不得再驳回（只能确认合格/不合格/特殊标注）；
- 被驳回工单：操作工必须处理（确认处理 或 申请驳回重审[备注必填]）后 badge 才消失；
  强制驳回（force_reject=true）只能申请驳回重审；
- 特殊标注工单：处理人可改写回合格/不合格（线下核实后），改写后转已复核。
"""
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.db import SessionLocal
from app.models import InspectionLog, ReviewRequest, User
from app.services.standards import compute_gaps

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("pending", "reapply")


def _now():
    return datetime.now(timezone.utc)


async def create_request(
    inspection_id: int, applicant_id: int | None, note: str, source: str = "operator_request"
) -> tuple[int, str]:
    """创建/复用复核工单；inspection 置 need_review。返回 (工单id, 工单状态)。"""
    async with SessionLocal() as session:
        insp = await session.get(InspectionLog, inspection_id)
        if insp is None:
            raise ValueError("检测记录不存在")
        active = (
            await session.execute(
                select(ReviewRequest)
                .where(
                    ReviewRequest.inspection_id == inspection_id,
                    ReviewRequest.status.in_(ACTIVE_STATUSES),
                )
                .limit(1)
            )
        ).scalar_one_or_none()
        if active is not None:
            return int(active.id), active.status
        req = ReviewRequest(
            inspection_id=inspection_id,
            applicant_id=applicant_id,
            source=source,
            status="pending",
            applicant_note=(note or "")[:300] or None,
        )
        session.add(req)
        insp.status = "need_review"
        insp.updated_at = _now()
        await session.commit()
        await session.refresh(req)
        return int(req.id), req.status


async def get_request(req_id: int) -> ReviewRequest | None:
    async with SessionLocal() as session:
        return await session.get(ReviewRequest, req_id)


def _role_cn(role: str | None) -> str:
    return {"operator": "操作工", "process_engineer": "工艺员", "admin": "管理员"}.get(role or "", role or "-")


async def _enrich(rows: list[ReviewRequest], applicant_first: bool) -> list[dict]:
    """工单 → 前端行结构（含检测信息、处理人/申请人姓名与角色）。"""
    async with SessionLocal() as session:
        insp_ids = {r.inspection_id for r in rows}
        user_ids = {r.applicant_id for r in rows if r.applicant_id} | {
            r.reviewer_id for r in rows if r.reviewer_id
        }
        insps = {}
        if insp_ids:
            for row in (
                await session.execute(select(InspectionLog).where(InspectionLog.id.in_(insp_ids)))
            ).scalars():
                insps[row.id] = row
        users = {}
        if user_ids:
            for u in (
                await session.execute(select(User).where(User.id.in_(user_ids)))
            ).scalars():
                users[u.id] = u

    out = []
    for r in rows:
        insp = insps.get(r.inspection_id)
        reviewer = users.get(r.reviewer_id)
        applicant = users.get(r.applicant_id)
        out.append(
            {
                "id": r.id,
                "inspection_id": r.inspection_id,
                "workpiece_no": insp.workpiece_no if insp else "-",
                "batch_no": insp.batch_no if insp else None,
                "system_status": insp.status if insp else "-",
                "review_status": r.status,
                "decision": r.decision,
                "applicant": (
                    f"{applicant.display_name or applicant.username}({applicant.id})"
                    if applicant
                    else "-"
                ),
                "applicant_id": r.applicant_id,
                "reviewer": f"{reviewer.display_name or reviewer.username}({reviewer.id})" if reviewer else "-",
                "reviewer_role": _role_cn(reviewer.role) if reviewer else "-",
                "comment": r.comment,
                "applicant_note": r.applicant_note,
                "force_reject": r.force_reject,
                "final_accepted": r.final_accepted,
                "created_at": r.created_at,
                "reviewed_at": r.reviewed_at,
                "reject_at": r.reject_at,
                "reapply_at": r.reapply_at,
                "inspection_created_at": insp.created_at if insp else None,
                # 详情弹窗数据（工艺/管理员视角可见；操作工走 /inspections/{id} 裁剪接口）
                "cv_result": insp.cv_result if insp else None,
                "standard_gaps": insp.standard_gaps if insp else None,
                "analysis_report": insp.analysis_report if insp else None,
                "image_key": insp.image_key if insp else None,
            }
        )
    return out


async def my_requests(
    user_id: int, role: str, box: str
) -> list[dict]:
    """「复核申请处理」页：申请人=当前用户。box: all|pending|rejected|reapply|special"""
    async with SessionLocal() as session:
        stmt = select(ReviewRequest).where(ReviewRequest.applicant_id == user_id)
        if box == "pending":
            stmt = stmt.where(ReviewRequest.status == "pending")
        elif box == "rejected":
            stmt = stmt.where(ReviewRequest.status == "rejected")
        elif box == "reapply":
            stmt = stmt.where(ReviewRequest.status == "reapply")
        elif box == "special":
            # 特殊标注库为全局（仅工艺/管理入口可见）
            stmt = select(ReviewRequest).where(ReviewRequest.status == "special")
        elif box == "done":
            stmt = stmt.where(ReviewRequest.status == "done")
        rows = list((await session.execute(stmt.order_by(ReviewRequest.id.desc()).limit(200))).scalars())
    return await _enrich(rows, applicant_first=True)


async def rejected_count(user_id: int) -> int:
    async with SessionLocal() as session:
        row = await session.execute(
            select(ReviewRequest.id).where(
                ReviewRequest.applicant_id == user_id,
                ReviewRequest.status == "rejected",
            )
        )
        return len(row.all())


async def workbench(box: str) -> list[dict]:
    """复核工作台（工艺/管理）：pending=待处理(pending+reapply) / done=已复核(含special) / all=全部"""
    async with SessionLocal() as session:
        stmt = select(ReviewRequest)
        if box == "pending":
            stmt = stmt.where(ReviewRequest.status.in_(ACTIVE_STATUSES))
        elif box == "done":
            stmt = stmt.where(ReviewRequest.status.in_(("done", "special")))
        rows = list((await session.execute(stmt.order_by(ReviewRequest.id.desc()).limit(200))).scalars())
    return await _enrich(rows, applicant_first=False)


async def decide(req_id: int, reviewer: User, decision: str, comment: str, force: bool) -> dict:
    """处理人处置。pending 与 reapply 均可处置；reapply 不得再驳回。"""
    if decision not in ("confirm_fail", "confirm_pass", "reject", "special"):
        raise ValueError("未知的复核结论")
    async with SessionLocal() as session:
        req = await session.get(ReviewRequest, req_id)
        if req is None:
            raise ValueError("复核工单不存在")
        if req.status not in ACTIVE_STATUSES:
            raise ValueError(f"工单当前状态为 {req.status}，不可处置")
        if req.status == "reapply" and decision == "reject":
            raise ValueError("驳回重审单不得再次驳回，请给出最终结论（合格/不合格/特殊标注）")

        insp = await session.get(InspectionLog, req.inspection_id)
        now = _now()
        if decision == "confirm_fail":
            insp.status = "fail"
            req.status, req.reviewed_at = "done", now
        elif decision == "confirm_pass":
            insp.status = "pass"
            req.status, req.reviewed_at = "done", now
        elif decision == "special":
            insp.status = "special"
            req.status, req.reviewed_at = "special", now
        elif decision == "reject":
            insp.status = "rechecking"
            req.status, req.reject_at = "rejected", now
            req.force_reject = bool(force)

        req.reviewer_id = reviewer.id
        req.decision = decision
        req.comment = (comment or "").strip() or None
        req.updated_at = now
        insp.updated_at = now
        await session.commit()
        return {"id": req.id, "status": req.status, "inspection_status": insp.status}


async def ack_rejection(req_id: int, user: User) -> dict:
    """操作工对被驳回工单"确认处理"（接受驳回结果；仅非强制驳回可用）。"""
    async with SessionLocal() as session:
        req = await session.get(ReviewRequest, req_id)
        if req is None or req.status != "rejected":
            raise ValueError("工单不存在或不在被驳回状态")
        if req.applicant_id != user.id:
            raise ValueError("只能处理本人的复核工单")
        if req.force_reject:
            raise ValueError("强制驳回重审单必须申请驳回重审，不能直接确认处理")
        now = _now()
        req.status = "done"
        req.final_accepted = True
        req.updated_at = now
        insp = await session.get(InspectionLog, req.inspection_id)
        if insp is not None:
            insp.status = "fail"  # 接受驳回=接受"不合格"处理结果
            insp.updated_at = now
        await session.commit()
        return {"id": req.id, "status": req.status}


async def reapply(req_id: int, user: User, note: str) -> dict:
    """操作工申请驳回重审（备注必填）；工单转 reapply 重新进入处理人队列。"""
    if not (note or "").strip():
        raise ValueError("申请驳回重审必须填写复核备注")
    async with SessionLocal() as session:
        req = await session.get(ReviewRequest, req_id)
        if req is None or req.status != "rejected":
            raise ValueError("工单不存在或不在被驳回状态")
        if req.applicant_id != user.id:
            raise ValueError("只能处理本人的复核工单")
        now = _now()
        req.status = "reapply"
        req.reapply_at = now
        req.applicant_note = note.strip()[:500]
        req.updated_at = now
        insp = await session.get(InspectionLog, req.inspection_id)
        if insp is not None:
            insp.status = "need_review"
            insp.updated_at = now
        await session.commit()
        return {"id": req.id, "status": req.status}


async def special_rewrite(req_id: int, reviewer: User, final: str, comment: str) -> dict:
    """处理人改写特殊标注为合格/不合格（线下核实后）。"""
    if final not in ("pass", "fail"):
        raise ValueError("改写结论只能是 pass 或 fail")
    async with SessionLocal() as session:
        req = await session.get(ReviewRequest, req_id)
        if req is None or req.status != "special":
            raise ValueError("工单不存在或不在特殊标注状态")
        now = _now()
        insp = await session.get(InspectionLog, req.inspection_id)
        insp.status = final
        insp.updated_at = now
        req.status = "done"
        req.reviewed_at = now
        req.reviewer_id = reviewer.id
        req.comment = f"[特殊标注改写为{final}] {(comment or '').strip()}".strip()
        req.updated_at = now
        await session.commit()
        return {"id": req.id, "status": req.status, "inspection_status": final}

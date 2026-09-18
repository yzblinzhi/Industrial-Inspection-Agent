"""复核工单 API：
- /reviews/my?box=        「复核申请处理」页（申请人视角，三角色）
- /reviews/rejected-count 侧栏被驳回感叹号
- /reviews/workbench?box= 复核工作台（工艺/管理）
- /reviews/{id}/decide | ack-rejection | reapply | special-rewrite
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.deps import get_current_user, require_role
from app.models import User
from app.services import audit
from app.services import review as review_service

router = APIRouter(prefix="/reviews", tags=["reviews"])


class DecideRequest(BaseModel):
    decision: str  # confirm_fail | confirm_pass | reject | special
    comment: str = ""
    force: bool = False


class ReapplyRequest(BaseModel):
    comment: str


class SpecialRewriteRequest(BaseModel):
    final: str  # pass | fail
    comment: str = ""


@router.get("/my")
async def my(box: str = "all", user: User = Depends(get_current_user)):
    return await review_service.my_requests(user.id, user.role, box)


@router.get("/rejected-count")
async def rejected_count(user: User = Depends(get_current_user)):
    return {"count": await review_service.rejected_count(user.id)}


@router.get("/workbench")
async def workbench(box: str = "pending", user: User = Depends(require_role("process_engineer", "admin"))):
    return await review_service.workbench(box)


@router.post("/{req_id}/decide")
async def decide(req_id: int, req: DecideRequest, user: User = Depends(require_role("process_engineer", "admin"))):
    try:
        result = await review_service.decide(req_id, user, req.decision, req.comment, req.force)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await audit.write_audit(user.id, "review_decide", "review_request", req_id,
                            {"decision": req.decision, "force": req.force})
    return result


@router.post("/{req_id}/ack-rejection")
async def ack_rejection(req_id: int, user: User = Depends(get_current_user)):
    try:
        result = await review_service.ack_rejection(req_id, user)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await audit.write_audit(user.id, "review_ack_rejection", "review_request", req_id)
    return result


@router.post("/{req_id}/reapply")
async def reapply(req_id: int, req: ReapplyRequest, user: User = Depends(get_current_user)):
    try:
        result = await review_service.reapply(req_id, user, req.comment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await audit.write_audit(user.id, "review_reapply", "review_request", req_id,
                            {"comment": req.comment})
    return result


@router.post("/{req_id}/special-rewrite")
async def special_rewrite(req_id: int, req: SpecialRewriteRequest,
                          user: User = Depends(require_role("process_engineer", "admin"))):
    try:
        result = await review_service.special_rewrite(req_id, user, req.final, req.comment)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await audit.write_audit(user.id, "review_special_rewrite", "review_request", req_id,
                            {"final": req.final})
    return result

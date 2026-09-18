"""检测记录：列表 / 详情（角色裁剪）/ 复核申请（操作工）/ 复核处置（工艺员）/ 报告下载。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.api.deps import get_current_user, require_role
from app.core.config import get_settings
from app.models import User
from app.schemas.inspection import (
    InspectionBrief,
    InspectionOutEngineer,
    InspectionOutOperator,
    RequestReviewRequest,
    ReviewRequest,
)
from app.services import inspection as inspection_service
from app.services import audit, storage

router = APIRouter(prefix="/inspections", tags=["inspections"])


@router.get("")
async def list_inspections(
    workpiece_no: str | None = None,
    batch_no: str | None = None,
    status: str | None = None,
    reviewed: bool | None = None,
    session_id: str | None = None,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
):
    rows, total = await inspection_service.list_logs(
        user.id, user.role, workpiece_no, batch_no, status, page, size, reviewed, session_id
    )
    return {
        "total": total,
        "items": [
            InspectionBrief(
                id=r.id,
                workpiece_no=r.workpiece_no,
                batch_no=r.batch_no,
                status=r.status,
                created_at=r.created_at,
                created_by=r.created_by,
            ).model_dump(mode="json")
            for r in rows
        ],
    }


@router.get("/database")
async def inspection_database(
    workpiece_no: str | None = None,
    status: str | None = None,
    page: int = 1,
    size: int = 20,
    user: User = Depends(get_current_user),
):
    """检测数据库（去重视图）：(工件号, 批次[空=未分批]) 去重，最新一次为准。
    全局可见；操作工字段裁剪（无量化数据/无 AI 分析参数）。"""
    items, total = await inspection_service.database_view(
        user.id, user.role, workpiece_no, status, page, size
    )
    if user.role == "operator":
        for it in items:
            it.pop("cv_result", None)
            it.pop("analysis_report", None)
            it.pop("image_key", None)
    return {"total": total, "items": items}


@router.get("/{inspection_id}")
async def detail(inspection_id: int, user: User = Depends(get_current_user)):
    row = await inspection_service.get_by_id(inspection_id)
    if row is None:
        raise HTTPException(404, "检测记录不存在")
    if user.role == "operator" and row.created_by != user.id:
        raise HTTPException(403, "无权查看他人检测记录")

    # 图片一律签 MinIO 签名 URL（<img> 无法携带 JWT，中转路径会 401）
    image_url = None
    if row.image_key:
        bucket, _, key = row.image_key.partition("/")
        try:
            image_url = storage.presign(bucket, key)
        except Exception:  # noqa: BLE001
            image_url = None
    data = inspection_service.to_out(row, user.role, image_url, None)
    model = InspectionOutOperator if user.role == "operator" else InspectionOutEngineer
    return model.model_validate(data).model_dump(mode="json")


@router.post("/{inspection_id}/request-review")
async def request_review(
    inspection_id: int,
    req: RequestReviewRequest,
    user: User = Depends(get_current_user),
):
    """操作工对本人检测记录发起复核申请 → 创建复核工单进入待复核队列。"""
    row = await inspection_service.get_by_id(inspection_id)
    if row is None:
        raise HTTPException(404, "检测记录不存在")
    if user.role == "operator" and row.created_by != user.id:
        raise HTTPException(403, "只能对本人检测记录申请复核")
    if row.status in ("pending", "detecting", "rechecking"):
        raise HTTPException(400, "该记录尚未出具检测结论，无法申请复核")

    from app.services import review as review_service

    req_id, status = await review_service.create_request(
        inspection_id, user.id, req.comment
    )
    await audit.write_audit(
        user.id, "request_review", "inspection", inspection_id, {"comment": req.comment}
    )
    return {
        "id": inspection_id,
        "request_id": req_id,
        "status": status,
        "message": "复核申请已提交" if status == "pending" else "该记录已在复核流程中",
    }


@router.post("/{inspection_id}/review")
async def review(
    inspection_id: int,
    req: ReviewRequest,
    user: User = Depends(require_role("process_engineer", "admin")),
):
    """复核处置（兼容入口）：转发到该检测记录的活跃复核工单。"""
    from app.services import review as review_service

    active = await review_service.workbench("pending")
    target = next((r for r in active if r["inspection_id"] == inspection_id), None)
    if target is None:
        raise HTTPException(404, "该检测记录无待处理的复核工单")
    try:
        result = await review_service.decide(
            target["id"], user, req.decision, req.comment, force=False
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    await audit.write_audit(
        user.id, "human_review", "inspection", inspection_id, {"decision": req.decision}
    )
    return {"id": inspection_id, "request_id": target["id"], "status": result["inspection_status"]}


@router.get("/{inspection_id}/report/download")
async def download_report(
    inspection_id: int,
    user: User = Depends(get_current_user),
):
    """报告内容直出（后端从 MinIO 取回，不经 307 跳转——跳转会触发浏览器跨域拦截）。
    所有登录角色可查看（操作工可查看，字段裁剪只作用于 JSON 接口）。"""
    s = get_settings()
    row = await inspection_service.get_by_id(inspection_id)
    if row is None or not row.report_file_key:
        raise HTTPException(404, "报告不存在")
    try:
        content = await storage.download_bytes(s.minio_report_bucket, row.report_file_key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"报告文件读取失败: {exc}") from exc
    return Response(content=content, media_type="text/markdown; charset=utf-8")

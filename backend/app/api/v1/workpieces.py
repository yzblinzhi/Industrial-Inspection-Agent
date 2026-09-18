"""工件与质检标准管理：查询全员可见，增改仅管理员（文档 2.1）。"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user, require_role
from app.core.db import SessionLocal
from app.models import QualityStandard, User, Workpiece
from app.schemas.workpiece import (
    StandardOut,
    StandardUpsertRequest,
    WorkpieceCreate,
    WorkpieceOut,
)
from app.services import audit

router = APIRouter(prefix="/workpieces", tags=["workpieces"])


@router.get("")
async def list_workpieces(user: User = Depends(get_current_user)):
    async with SessionLocal() as session:
        rows = (
            await session.execute(
                select(Workpiece).options(selectinload(Workpiece.standards))
            )
        ).scalars().all()
    return [
        WorkpieceOut(
            id=wp.id,
            workpiece_no=wp.workpiece_no,
            name=wp.name,
            material=wp.material,
            coating_spec=wp.coating_spec,
            description=wp.description,
            created_at=wp.created_at,
            standards=[StandardOut.model_validate(std, from_attributes=True) for std in wp.standards],
        ).model_dump(mode="json")
        for wp in rows
    ]


@router.post("")
async def create_workpiece(
    req: WorkpieceCreate, user: User = Depends(require_role("admin"))
):
    async with SessionLocal() as session:
        exists = (
            await session.execute(
                select(Workpiece).where(Workpiece.workpiece_no == req.workpiece_no)
            )
        ).scalar_one_or_none()
        if exists:
            raise HTTPException(409, "工件型号编号已存在")
        wp = Workpiece(
            workpiece_no=req.workpiece_no,
            name=req.name,
            material=req.material,
            coating_spec=req.coating_spec,
            description=req.description,
            created_by=user.id,
        )
        session.add(wp)
        await session.flush()
        for std in req.standards:
            session.add(QualityStandard(workpiece_id=wp.id, **std.model_dump()))
        await session.commit()
        await audit.write_audit(user.id, "create_workpiece", "workpiece", wp.id)
        return {"id": wp.id, "workpiece_no": wp.workpiece_no}


@router.put("/{workpiece_id}/standards")
async def upsert_standards(
    workpiece_id: int,
    req: StandardUpsertRequest,
    user: User = Depends(require_role("admin")),
):
    async with SessionLocal() as session:
        wp = await session.get(Workpiece, workpiece_id)
        if wp is None:
            raise HTTPException(404, "工件不存在")
        # 全量替换该工件的标准（V1.0 语义：管理员以最新配置为准）
        olds = (
            await session.execute(
                select(QualityStandard).where(QualityStandard.workpiece_id == workpiece_id)
            )
        ).scalars().all()
        for old in olds:
            await session.delete(old)
        for std in req.standards:
            session.add(QualityStandard(workpiece_id=workpiece_id, **std.model_dump()))
        await session.commit()
        await audit.write_audit(user.id, "update_standard", "workpiece", workpiece_id)
    return {"ok": True, "count": len(req.standards)}

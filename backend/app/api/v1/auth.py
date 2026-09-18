from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.api.deps import get_current_user
from app.core.db import SessionLocal
from app.core.security import create_access_token, verify_password
from app.models import User
from app.schemas.auth import LoginRequest, MeResponse, TokenResponse
from app.services import audit

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    async with SessionLocal() as session:
        user = (
            await session.execute(select(User).where(User.username == req.username))
        ).scalar_one_or_none()
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    token = create_access_token(user.id, user.role)
    await audit.write_audit(user.id, "login", "user", user.id)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        username=user.username,
        role=user.role,
        display_name=user.display_name,
    )


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(get_current_user)):
    return MeResponse(
        user_id=user.id, username=user.username, role=user.role, display_name=user.display_name
    )

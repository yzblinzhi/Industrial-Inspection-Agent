"""文件访问中转：私有桶 → 307 跳 MinIO 签名 URL（文档 8.1）。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse

from app.api.deps import get_current_user
from app.models import User
from app.services import storage

router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{file_key:path}")
async def get_file(file_key: str, user: User = Depends(get_current_user)):
    bucket, _, key = file_key.partition("/")
    if not key:
        raise HTTPException(400, "路径格式应为 {bucket}/{key}")
    if bucket not in storage.ALLOWED_BUCKETS:
        raise HTTPException(403, "禁止访问该存储桶")
    try:
        url = storage.presign(bucket, key)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"对象存储不可用: {exc}") from exc
    return RedirectResponse(url, status_code=307)

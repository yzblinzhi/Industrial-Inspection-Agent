"""图片上传：入 MinIO 私有桶，返回 object key 与预览 URL（文档 9.1）。"""
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.models import User
from app.schemas.chat import UploadResponse
from app.services import audit, storage

router = APIRouter(prefix="/upload", tags=["upload"])

ALLOWED_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_SIZE = 20 * 1024 * 1024


@router.post("/image", response_model=UploadResponse)
async def upload_image(file: UploadFile, user: User = Depends(get_current_user)):
    s = get_settings()
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(400, f"仅支持 {', '.join(sorted(ALLOWED_EXTS))} 格式")
    data = await file.read()
    if len(data) > MAX_SIZE:
        raise HTTPException(400, "图片超过 20MB 限制")

    key = f"{datetime.now():%Y/%m}/{uuid.uuid4().hex}{ext}"
    try:
        await storage.upload_bytes(
            s.minio_image_bucket, key, data, content_type=file.content_type or "image/jpeg"
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"对象存储不可用，请确认 MinIO 容器已启动: {exc}") from exc

    image_key = f"{s.minio_image_bucket}/{key}"
    await audit.write_audit(user.id, "upload_image", "inspection", image_key)
    # 预览直接给 MinIO 签名 URL（自带鉴权、30 分钟有效），<img> 标签无需携带 JWT
    return UploadResponse(image_key=image_key, preview_url=storage.presign(s.minio_image_bucket, key))

"""MinIO 存储服务：私有桶 + 上传/文本写入/签名 URL/删除（补偿用，文档 8）。"""
import asyncio
import io
import logging
from datetime import timedelta

from minio import Minio

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def get_minio() -> Minio:
    s = get_settings()
    return Minio(
        s.minio_endpoint,
        access_key=s.minio_access_key,
        secret_key=s.minio_secret_key,
        secure=s.minio_secure,
    )


ALLOWED_BUCKETS = {get_settings().minio_image_bucket, get_settings().minio_report_bucket}


async def upload_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    def _put():
        client = get_minio()
        client.put_object(
            bucket, key, io.BytesIO(data), length=len(data), content_type=content_type
        )

    await asyncio.to_thread(_put)


async def upload_text(bucket: str, key: str, text: str, content_type: str = "text/markdown; charset=utf-8") -> None:
    await upload_bytes(bucket, key, text.encode("utf-8"), content_type)


async def download_bytes(bucket: str, key: str) -> bytes:
    def _get():
        client = get_minio()
        resp = client.get_object(bucket, key)
        try:
            return resp.read()
        finally:
            resp.close()
            resp.release_conn()

    return await asyncio.to_thread(_get)


def presign(bucket: str, key: str, expires_sec: int | None = None) -> str:
    """签名 GET URL（默认 30 分钟），同步且廉价，可直接在事件循环中调用。"""
    s = get_settings()
    client = get_minio()
    return client.presigned_get_object(
        bucket, key, expires=timedelta(seconds=expires_sec or s.presign_expire_sec)
    )


async def delete_object(bucket: str, key: str) -> None:
    def _rm():
        get_minio().remove_object(bucket, key)

    await asyncio.to_thread(_rm)


def bucket_exists(bucket: str) -> bool:
    return get_minio().bucket_exists(bucket)

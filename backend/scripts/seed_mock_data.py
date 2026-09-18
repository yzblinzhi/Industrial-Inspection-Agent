"""灌入 Mock 数据：
1. 为每个评测场景上传 1x1 占位 JPEG 到 inspection-images/mock/{scene}.jpg
   （真实场景演示时替换为实际喷涂照片即可）；
2. 若 RAG_PROVIDER=redis_vector，则把工艺文档向量化写入 Redis DB0 并建索引。
用法（backend 目录）：uv run python scripts/seed_mock_data.py
"""
import base64
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

# 1x1 白色像素 JPEG（占位图，仅保证上传/预览链路可通）
TINY_JPEG = base64.b64decode(
    "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
    "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
    "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
)

SCENES = [
    "S1_flange_pass", "S2_column_sagging", "S3_panel_color",
    "S4_door_mixed", "S5_low_confidence",
]


async def seed_images() -> None:
    from app.core.config import get_settings
    from app.services.storage import get_minio

    s = get_settings()
    client = get_minio()
    if not client.bucket_exists(s.minio_image_bucket):
        client.make_bucket(s.minio_image_bucket)
    for scene in SCENES:
        key = f"mock/{scene}.jpg"
        from io import BytesIO

        client.put_object(
            s.minio_image_bucket, key, BytesIO(TINY_JPEG), length=len(TINY_JPEG), content_type="image/jpeg"
        )
        print(f"[seed] 上传 {s.minio_image_bucket}/{key}")


async def seed_vectors() -> None:
    from app.core.config import get_settings
    from app.providers.factory import get_llm_provider

    s = get_settings()
    if s.rag_provider != "redis_vector":
        print("[seed] RAG_PROVIDER != redis_vector，跳过向量灌库")
        return
    import json

    import redis
    from app.providers.rag_redis import PREFIX, create_index
    from app.providers.rag_mock import _parse_front_matter

    client = redis.from_url(s.redis_vector_dsn, decode_responses=True)
    create_index(client)
    docs_dir = Path(s.mock_data_dir) / "knowledge"
    import struct

    for f in sorted(docs_dir.glob("*.md")):
        meta, body = _parse_front_matter(f.read_text(encoding="utf-8"))
        text_for_embed = f"{meta.get('title', '')}\n{body}"
        vec = (await get_llm_provider().embed([text_for_embed]))[0]
        client.hset(
            PREFIX + meta.get("doc_id", f.stem),
            mapping={
                "doc_id": meta.get("doc_id", f.stem),
                "title": meta.get("title", f.stem),
                "text": body,
                "params": json.dumps(meta.get("params", {}), ensure_ascii=False),
                "vec": struct.pack(f"{len(vec)}f", *vec),
            },
        )
        print(f"[seed] 向量化写入 {meta.get('doc_id', f.stem)}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(seed_images())
    asyncio.run(seed_vectors())
    print("[seed] 完成")

"""初始化 MinIO 私有桶（幂等）：inspection-images / reports。
用法（backend 目录）：uv run python scripts/init_buckets.py
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))


def main() -> None:
    from app.core.config import get_settings
    from app.services.storage import get_minio

    s = get_settings()
    client = get_minio()
    for bucket in (s.minio_image_bucket, s.minio_report_bucket):
        if client.bucket_exists(bucket):
            print(f"[init_buckets] 桶已存在: {bucket}")
        else:
            client.make_bucket(bucket)
            print(f"[init_buckets] 桶已创建(默认私有): {bucket}")
    print("[init_buckets] 完成。桶策略为 private，前端访问一律走签名 URL。")


if __name__ == "__main__":
    main()

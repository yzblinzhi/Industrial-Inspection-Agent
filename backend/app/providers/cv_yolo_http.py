"""真实 YOLO HTTP 推理服务实现（V2.0 启用）：契约与 cv_mock 完全一致。
当前仅占位——CV_PROVIDER=yolo_http 时抛出未部署异常。"""
import httpx

from app.providers.base import CVProvider


class YoloHttpProvider(CVProvider):
    def __init__(self, endpoint: str = "http://localhost:9100/detect") -> None:
        self.endpoint = endpoint

    async def detect(self, image_key: str, workpiece_no: str) -> dict:
        # 真实实现：向后端推理服务提交 image_url（MinIO 签名 URL），返回同构 JSON
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                self.endpoint, json={"image_key": image_key, "workpiece_no": workpiece_no}
            )
            resp.raise_for_status()
            return resp.json()

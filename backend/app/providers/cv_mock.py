"""CV Mock：随机抽取 mock_data/cv_results/*.json 预置场景（概率方式，每个工件每次检测
都可能命中任意场景）。返回结构与真实 YOLO 服务完全一致（CVResult 契约）。"""
import json
import logging
import random
from pathlib import Path

from app.core.config import get_settings
from app.providers.base import CVProvider
from app.schemas.cv import CVResult

logger = logging.getLogger(__name__)


class MockCVProvider(CVProvider):
    def __init__(self) -> None:
        self.dir = Path(get_settings().mock_data_dir) / "cv_results"

    def _load_all(self) -> list[dict]:
        if not self.dir.exists():
            logger.warning("mock cv_results 目录不存在: %s", self.dir)
            return []
        results = []
        for f in sorted(self.dir.glob("*.json")):
            try:
                results.append(json.loads(f.read_text(encoding="utf-8")))
            except Exception as exc:  # noqa: BLE001
                logger.error("mock 结果文件损坏 %s: %s", f.name, exc)
        return results

    async def detect(self, image_key: str, workpiece_no: str) -> dict:
        all_results = self._load_all()
        if not all_results:
            raise RuntimeError("无可用 mock CV 结果，请先运行 scripts/seed_mock_data.py")

        mode = get_settings().cv_mock_mode
        chosen = None
        if mode == "match":  # 确定性：按工件号固定场景（评测回归用）
            chosen = next(
                (r for r in all_results if r.get("workpiece_no") == workpiece_no), None
            )
        if chosen is None:  # 概率方式：随机抽场景，任何工件都可能命中任意场景
            chosen = random.choice(all_results)
        logger.info(
            "Mock CV 场景(%s): %s -> %s(%s)", mode, workpiece_no or image_key,
            chosen.get("scene"), chosen.get("workpiece_no"),
        )

        chosen = {**chosen, "image_key": image_key}
        chosen.setdefault("meta", {})["scene"] = chosen.get("scene", "unknown")
        result = CVResult.model_validate(chosen)
        return result.model_dump()

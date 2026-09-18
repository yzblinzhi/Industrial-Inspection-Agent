"""CV Mock 契约校验：mock_data/cv_results 全部场景 JSON 必须满足 CVResult 契约。"""
import json
from pathlib import Path

import pytest

from app.schemas.cv import CVResult

MOCK_DIR = Path(__file__).resolve().parents[2] / "mock_data" / "cv_results"
JSON_FILES = sorted(MOCK_DIR.glob("*.json"))


def test_mock_dir_exists():
    assert MOCK_DIR.exists(), f"mock 目录不存在: {MOCK_DIR}"


@pytest.mark.parametrize("f", JSON_FILES, ids=lambda p: p.name)
def test_scene_json_fits_contract(f):
    raw = json.loads(f.read_text(encoding="utf-8"))
    # cv_mock 在 detect 时注入 image_key（场景文件只含预置结果）
    raw.setdefault("image_key", f"inspection-images/mock/{f.stem}.jpg")
    result = CVResult.model_validate(raw)  # workpiece_no/scene 为多余字段应被忽略
    for det in result.detections:
        x1, y1, x2, y2 = det.bbox_xyxy
        assert x1 < x2 and y1 < y2
        assert 0 <= det.confidence <= 1

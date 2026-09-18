"""标准比对纯函数单测（不依赖 DB / LLM）。"""
from app.services.standards import compute_gaps

STD_SAG_5 = {"standard_id": 1, "defect_type": "sagging", "max_area_cm2": 5.0,
             "max_count": 2, "max_dimension_mm": None, "confidence_threshold": 0.6, "extra_rules": {}}
STD_COLOR = {"standard_id": 2, "defect_type": "color_deviation", "max_area_cm2": None,
             "max_count": None, "max_dimension_mm": None, "confidence_threshold": 0.6,
             "extra_rules": {"max_delta_e": 1.5}}


def _cv(detections):
    return {"model": "m", "image_key": "k", "image_size": {"width": 1920, "height": 1080},
            "detections": detections, "meta": {}}


def test_s1_pass_no_detections():
    gaps, suspects = compute_gaps(_cv([]), [STD_SAG_5])
    assert gaps == [] and suspects == []


def test_s2_sagging_exceed_136():
    det = [{"id": 1, "defect_type": "sagging", "confidence": 0.87,
            "bbox_xyxy": [1, 2, 3, 4], "measure": {"area_cm2": 6.8, "max_length_mm": 42.0}}]
    gaps, suspects = compute_gaps(_cv(det), [STD_SAG_5])
    assert len(gaps) == 1
    assert gaps[0]["defect_type"] == "sagging" and gaps[0]["exceed_ratio"] == 1.36
    assert suspects == []


def test_s3_delta_e_exceed():
    det = [{"id": 1, "defect_type": "color_deviation", "confidence": 0.78,
            "bbox_xyxy": [1, 2, 3, 4], "measure": {"delta_e": 2.1}}]
    gaps, _ = compute_gaps(_cv(det), [STD_COLOR])
    assert len(gaps) == 1 and gaps[0]["exceed_ratio"] == 1.4


def test_s4_multiple_gaps():
    dets = [
        {"id": 1, "defect_type": "sagging", "confidence": 0.9, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 5.6}},
        {"id": 2, "defect_type": "orange_peel", "confidence": 0.82, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 3.2}},
        {"id": 3, "defect_type": "particle", "confidence": 0.74, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 0.8}},
    ]
    stds = [
        STD_SAG_5,
        {"standard_id": 3, "defect_type": "orange_peel", "max_area_cm2": 2.5, "max_count": None,
         "max_dimension_mm": None, "confidence_threshold": 0.6, "extra_rules": {}},
        {"standard_id": 4, "defect_type": "particle", "max_area_cm2": 0.5, "max_count": None,
         "max_dimension_mm": None, "confidence_threshold": 0.6, "extra_rules": {}},
    ]
    gaps, suspects = compute_gaps(_cv(dets), stds)
    assert {g["defect_type"] for g in gaps} == {"sagging", "orange_peel", "particle"}
    assert suspects == []


def test_s5_low_confidence_only_suspects():
    dets = [
        {"id": 1, "defect_type": "sagging", "confidence": 0.42, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 2.0}},
        {"id": 2, "defect_type": "particle", "confidence": 0.38, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 0.3}},
    ]
    gaps, suspects = compute_gaps(_cv(dets), [STD_SAG_5])
    assert gaps == []
    assert {s["detection_id"] for s in suspects} == {1, 2}


def test_count_exceed():
    dets = [
        {"id": i, "defect_type": "sagging", "confidence": 0.9, "bbox_xyxy": [0, 0, 1, 1],
         "measure": {"area_cm2": 1.0}}
        for i in (1, 2, 3)
    ]
    gaps, _ = compute_gaps(_cv(dets), [STD_SAG_5])
    assert any(g["gap_kind"] == "count" and g["actual"]["count"] == 3 for g in gaps)


def test_no_standard_for_type_ignored():
    det = [{"id": 1, "defect_type": "scratch", "confidence": 0.9,
            "bbox_xyxy": [0, 0, 1, 1], "measure": {"area_cm2": 9.9}}]
    gaps, suspects = compute_gaps(_cv(det), [STD_SAG_5])
    assert gaps == [] and suspects == []

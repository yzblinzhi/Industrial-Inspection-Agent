"""自检硬规则单测：不依赖 LLM，验证五条规则各自的拦截能力。"""
from app.graph.nodes.self_reflection import run_hard_rules

GAPS = [{"detection_id": 1, "defect_type": "sagging",
         "actual": {"area_cm2": 6.8}, "limit": {"area_cm2": 5.0},
         "exceed_ratio": 1.36, "gap_kind": "measure"}]

RAG = [{"doc_id": "rag-sagging-001", "title": "流挂处置", "score": 0.9,
        "text": "喷涂压力调整至 0.30~0.40 MPa，黏度控制在 18~24 s。",
        "params": {"喷涂压力_MPa": [0.30, 0.40]}}]

CV = {"detections": [{"id": 1, "defect_type": "sagging", "confidence": 0.87,
                      "bbox_xyxy": [1, 2, 3, 4], "measure": {"area_cm2": 6.8}}]}


def _report(**kw):
    base = {
        "conclusion": "fail",
        "root_cause": "涂料黏度偏低，湿膜过厚垂流",
        "suggestions": [{"defect_type": "sagging", "param_name": "喷涂压力",
                         "param_value": "0.35 MPa", "action": "调整压力", "source": "rag_sagging"}],
        "summary_text": "流挂实测 6.8 cm²，标准限值 5.0 cm²，超标 1.36 倍；建议调整喷涂压力至 0.35 MPa。",
    }
    base.update(kw)
    return base


def test_good_report_passes():
    assert run_hard_rules(_report(), GAPS, RAG, CV) == []


def test_r1_conclusion_mismatch():
    v = run_hard_rules(_report(conclusion="pass"), GAPS, RAG, CV)
    assert any(x.startswith("R1") for x in v)


def test_r1_fail_with_suspects_only_ok():
    """fail + 仅低置信度可疑项（无超标项）应放行（保守判定场景）。"""
    suspects = [{"detection_id": 1, "defect_type": "sagging", "confidence": 0.42, "threshold": 0.6}]
    v = run_hard_rules(_report(), [], RAG, CV, None, suspects)
    assert not any(x.startswith("R1") for x in v)


def test_r2_fabricated_defect_type():
    bad = _report()
    bad["suggestions"] = [{**bad["suggestions"][0], "defect_type": "pinhole"}]
    v = run_hard_rules(bad, GAPS, RAG, CV)
    assert any(x.startswith("R2") for x in v)


def test_r3_param_out_of_range():
    bad = _report()
    bad["suggestions"] = [{**bad["suggestions"][0], "param_value": "0.80 MPa"}]
    v = run_hard_rules(bad, GAPS, RAG, CV)
    assert any(x.startswith("R3") for x in v)


def test_r4_untraceable_number():
    v = run_hard_rules(_report(summary_text="流挂实测 6.8 cm²，建议打磨至 3000 目后复检。"), GAPS, RAG, CV)
    assert any(x.startswith("R4") for x in v)


def test_r5_hedge_words():
    v = run_hard_rules(_report(root_cause="可能是黏度偏低"), GAPS, RAG, CV)
    assert any(x.startswith("R5") for x in v)


def test_pass_case_with_empty_gaps_ok():
    v = run_hard_rules(_report(conclusion="pass", suggestions=[],
                               summary_text="各检测项均在标准限值内。"), [], [], {"detections": []})
    assert v == []

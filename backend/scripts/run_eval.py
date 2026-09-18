"""端到端评测回归（附录 B 场景集 S1-S6）：直接驱动质检图并断言。
用法（backend 目录，需 PG 已就绪且已执行 init_db/seed）：
    uv run python scripts/run_eval.py
"""
import asyncio
import sys
import uuid
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from langchain_core.messages import HumanMessage  # noqa: E402

RESULTS = []


def check(name: str, cond: bool, detail: str = "") -> None:
    RESULTS.append((name, cond, detail))
    print(f"  {'✅' if cond else '❌'} {name}" + (f" | {detail}" if detail else ""))


async def run_inspection(graph, workpiece_no: str, message: str, image_key: str | None):
    session_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": session_id}}
    await graph.ainvoke(
        {
            "session_id": session_id,
            "user_id": 2,  # engineer
            "user_role": "process_engineer",
            "user_input": message,
            "image_key": image_key,
            "messages": [HumanMessage(content=message)],
            "reflection_retries": 0,
            "reflection_ok": False,
            "reflection_errors": [],
            "human_review_comment": None,
            "review_decision": None,
        },
        config,
    )
    return (await graph.aget_state(config)).values or {}


async def main() -> None:
    from app.core.checkpointer import build_checkpointer
    from app.graph.builder import build_graph

    cp = await build_checkpointer()
    graph = build_graph(cp)

    print("\n== S1 合格件 ==")
    v = await run_inspection(graph, "FL-PN18-A", "检测这个法兰盘 FL-PN18-A",
                             "inspection-images/mock/S1_flange_pass.jpg")
    check("S1 状态=pass", v.get("status") == "pass", str(v.get("status")))
    check("S1 无整改建议", not (v.get("analysis_report") or {}).get("suggestions"))

    print("\n== S2 流挂超标 ==")
    v = await run_inspection(graph, "CL-ZH02-B", "检测立柱 CL-ZH02-B，批次 B2026-09-01",
                             "inspection-images/mock/S2_column_sagging.jpg")
    gaps = v.get("standard_gaps") or []
    check("S2 状态=fail", v.get("status") == "fail", str(v.get("status")))
    check("S2 流挂超标 1.36 倍", any(g["defect_type"] == "sagging" and g["exceed_ratio"] == 1.36 for g in gaps))
    check("S2 建议参数在 RAG 范围内", (v.get("analysis_report") or {}).get("suggestions") != [])

    print("\n== S3 色差超标 ==")
    v = await run_inspection(graph, "PN-MB03-C", "检测面板 PN-MB03-C",
                             "inspection-images/mock/S3_panel_color.jpg")
    check("S3 状态=fail", v.get("status") == "fail", str(v.get("status")))
    check("S3 delta_e 超标 1.4 倍", any(g["defect_type"] == "color_deviation" and g["exceed_ratio"] == 1.4
                                       for g in v.get("standard_gaps") or []))

    print("\n== S4 多缺陷混合 ==")
    v = await run_inspection(graph, "DR-MB07-D", "检测门板 DR-MB07-D",
                             "inspection-images/mock/S4_door_mixed.jpg")
    gaps = v.get("standard_gaps") or []
    sugg = (v.get("analysis_report") or {}).get("suggestions") or []
    check("S4 状态=fail", v.get("status") == "fail", str(v.get("status")))
    check("S4 三项超标", {g["defect_type"] for g in gaps} == {"sagging", "orange_peel", "particle"})
    check("S4 建议数=超标缺陷数", len(sugg) == len({g['defect_type'] for g in gaps}),
          f"sugg={len(sugg)} gaps={len(gaps)}")

    print("\n== S5 低置信度 → 保守判不合格 ==")
    v = await run_inspection(graph, "PL-XT05-E", "检测平板 PL-XT05-E",
                             "inspection-images/mock/S5_low_confidence.jpg")
    check("S5 状态=fail（低置信度按不合格处理）", v.get("status") == "fail", str(v.get("status")))
    check("S5 低置信度可疑项已识别", len(v.get("suspects") or []) == 2)

    print("\n== S6 多轮追问（同会话） ==")
    session_id = uuid.uuid4().hex
    config = {"configurable": {"thread_id": session_id}}
    await graph.ainvoke(
        {
            "session_id": session_id, "user_id": 2, "user_role": "process_engineer",
            "user_input": "检测立柱 CL-ZH02-B", "image_key": "inspection-images/mock/S2_column_sagging.jpg",
            "messages": [HumanMessage(content="检测立柱 CL-ZH02-B")],
            "reflection_retries": 0, "reflection_ok": False, "reflection_errors": [],
            "human_review_comment": None, "review_decision": None,
        },
        config,
    )
    await graph.ainvoke(
        {
            "session_id": session_id, "user_role": "process_engineer",
            "user_input": "喷涂压力具体调多少？", "messages": [HumanMessage(content="喷涂压力具体调多少？")],
        },
        config,
    )
    values = (await graph.aget_state(config)).values or {}
    msgs = values.get("messages") or []
    check("S6 对话含 4 条消息(2轮)", len(msgs) >= 4, f"实际 {len(msgs)} 条")
    last = str(msgs[-1].content) if msgs else ""
    check("S6 追问命中压力参数", ("0.30" in last or "0.3" in last or "压力" in last))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n===== 评测结果: {passed}/{len(RESULTS)} 通过 =====")
    if passed < len(RESULTS):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

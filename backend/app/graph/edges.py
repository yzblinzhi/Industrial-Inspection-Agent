"""条件路由边：全部依据 State 显式字段判定（文档 5.3）。
检测结论只有 pass / fail 两态；复核由操作工主动申请（review_request）+ 工艺员工作台处置。"""


def route_after_parse(state: dict) -> str:
    intent = state.get("intent")
    if intent == "need_guidance":
        return "finish"  # 缺工件号：已返回填报指引，直接结束
    if intent == "request_review":
        return "review"
    if intent == "new_inspection" and state.get("image_key") and (
        state.get("workpiece_info") or {}
    ).get("workpiece_no"):
        return "inspect"
    return "qa"


def route_after_validate(state: dict) -> str:
    # 比对后一律走完整 LLM 流程（RAG→推理→自检），不确定项（无标准/低置信度）
    # 以 validator_notice 进入推理上下文，不再直出固定文案
    if state.get("standard_gaps") or state.get("suspects") or state.get("validator_notice"):
        return "retrieval"
    return "reason"  # 合格件同样走 LLM 生成分析


def route_after_reflection(state: dict) -> str:
    # 自检不过 → 回流 reasoning 重生成（上限 2 次，超限由 reflection 节点强制判不合格）
    return "report" if state.get("reflection_ok") else "regen"

"""LangGraph AgentState：业务字段存"最近一次检测快照"，messages 存对话流（文档 5.1）。"""
from typing import Annotated, Literal, Optional

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

InspectionStatus = Literal[
    "pending", "detecting", "pass", "fail", "need_review", "rechecking"
]


class AgentState(TypedDict, total=False):
    # ---- 会话与对话 ----
    session_id: str  # = LangGraph thread_id
    user_id: int
    user_role: str  # operator | process_engineer | admin（qa 回答按角色裁剪）
    user_input: str
    messages: Annotated[list[BaseMessage], add_messages]

    # ---- 检测输入 ----
    image_key: Optional[str]  # MinIO object key（绝不传 base64！）
    image_url: Optional[str]  # 后端签发的预览 URL
    inspection_uid: Optional[str]  # 本轮检测单据标识（每轮检测独立成单）
    workpiece_info: dict  # {workpiece_no, name, batch_no, coating_spec}

    # ---- 流转中间产物 ----
    intent: str  # new_inspection | history_query | followup_qa
    cv_result: dict  # CVProvider 契约 JSON
    standard_gaps: list[dict]  # 超标项
    suspects: list[dict]  # 低置信度可疑项（不足判定 → need_review）
    validator_notice: Optional[str]  # 比对阶段给用户的提示（如未配置标准）
    rag_context: str
    rag_docs: list[dict]
    analysis_report: dict  # ReasoningReport
    report_file_key: Optional[str]  # 归档报告 MinIO key

    # ---- 流程控制 ----
    status: InspectionStatus
    last_inspection_id: Optional[int]  # 复检/对比预留
    reflection_retries: int
    reflection_ok: bool
    reflection_errors: list[str]
    review_decision: Optional[str]  # confirm | revalidate | reject（interrupt 恢复后写入）
    human_review_comment: Optional[str]

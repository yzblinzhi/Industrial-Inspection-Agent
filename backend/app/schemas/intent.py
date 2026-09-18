"""意图解析与问答结构化契约。"""
from typing import Literal

from pydantic import BaseModel, Field


class IntentParse(BaseModel):
    """input_parser 节点的结构化输出。"""

    intent: Literal[
        "new_inspection", "history_query", "followup_qa", "request_review", "need_guidance"
    ] = Field(default="followup_qa")
    workpiece_no: str | None = None
    batch_no: str | None = None


class QaAnswer(BaseModel):
    """qa_answer 节点的结构化输出。"""

    answer: str

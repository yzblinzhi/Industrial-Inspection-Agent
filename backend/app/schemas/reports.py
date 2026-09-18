"""ReasoningReport 契约：推理节点结构化输出 + 自检校验对象（文档 5.2）。"""
from typing import Literal

from pydantic import BaseModel, Field


class Suggestion(BaseModel):
    defect_type: str = Field(description="必须来自 standard_gaps 中出现的缺陷类型")
    param_name: str = Field(description="工艺参数名，如 喷涂压力")
    param_value: str = Field(description="建议值，如 0.35 MPa")
    action: str = Field(description="整改动作描述")
    source: str = Field(description="溯源标识：rag_{doc_id} 或 standard_{id}")


class ReasoningReport(BaseModel):
    conclusion: Literal["pass", "fail", "need_review"]
    root_cause: str = ""
    suggestions: list[Suggestion] = Field(default_factory=list)
    summary_text: str = Field(default="", description="前端展示 Markdown 文本，所有数值须可溯源")

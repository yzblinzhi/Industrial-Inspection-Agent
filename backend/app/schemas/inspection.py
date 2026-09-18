"""检测记录响应模型：按角色裁剪字段（权限在后端，文档 9.3）。"""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ---- 操作工视图：无量化值、无工艺参数建议 ----
class InspectionOutOperator(BaseModel):
    id: int
    session_id: str
    workpiece_no: str
    batch_no: str | None
    status: str
    conclusion_text: str = ""  # 仅结论性文字
    annotated_image_url: str | None = None
    created_at: datetime
    review_comment: str | None = None


# ---- 工艺员/管理员视图：全量 ----
class InspectionOutEngineer(InspectionOutOperator):
    workpiece_id: int | None = None
    image_key: str | None = None
    image_url: str | None = None
    cv_result: dict | None = None
    standard_gaps: list | None = None
    analysis_report: dict | None = None
    report_file_key: str | None = None
    report_url: str | None = None
    reviewed_by: int | None = None
    reviewed_at: datetime | None = None


class InspectionBrief(BaseModel):
    id: int
    workpiece_no: str
    batch_no: str | None
    status: str
    created_at: datetime
    created_by: int | None


class ReviewRequest(BaseModel):
    decision: Literal["confirm_fail", "confirm_pass", "reject", "special"]
    comment: str = ""
    force: bool = False  # 驳回重检时是否强制驳回重审


class RequestReviewRequest(BaseModel):
    """操作工复核申请。"""

    comment: str = ""

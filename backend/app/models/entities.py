"""SQLAlchemy ORM：6 张核心表（users / workpieces / quality_standards /
inspection_logs / conversations / audit_logs），DDL 与文档 7.2 一致。"""
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(128))
    role: Mapped[str] = mapped_column(String(16))  # operator | process_engineer | admin
    display_name: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Workpiece(Base):
    __tablename__ = "workpieces"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workpiece_no: Mapped[str] = mapped_column(String(64), unique=True)
    name: Mapped[str] = mapped_column(String(128))
    material: Mapped[str | None] = mapped_column(String(64))
    coating_spec: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    standards: Mapped[list["QualityStandard"]] = relationship(
        back_populates="workpiece", cascade="all, delete-orphan"
    )


class QualityStandard(Base):
    __tablename__ = "quality_standards"
    __table_args__ = (Index("uq_std_workpiece_defect", "workpiece_id", "defect_type", unique=True),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    workpiece_id: Mapped[int] = mapped_column(ForeignKey("workpieces.id", ondelete="CASCADE"))
    defect_type: Mapped[str] = mapped_column(String(64))
    max_area_cm2: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    max_count: Mapped[int | None] = mapped_column(Integer)
    max_dimension_mm: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    confidence_threshold: Mapped[Decimal | None] = mapped_column(Numeric(4, 3))
    extra_rules: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

    workpiece: Mapped["Workpiece"] = relationship(back_populates="standards")


class InspectionLog(Base):
    __tablename__ = "inspection_logs"
    __table_args__ = (
        Index("idx_inspection_workpiece", "workpiece_no", "created_at"),
        Index("idx_inspection_batch", "batch_no"),
        Index("idx_inspection_session", "session_id"),
        Index("idx_inspection_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64))
    inspection_uid: Mapped[str | None] = mapped_column(
        String(64), unique=True
    )  # 每轮检测唯一标识：同会话多次检测各自独立成单
    workpiece_id: Mapped[int | None] = mapped_column(ForeignKey("workpieces.id"))
    workpiece_no: Mapped[str] = mapped_column(String(64))
    batch_no: Mapped[str | None] = mapped_column(String(64))
    image_key: Mapped[str | None] = mapped_column(String(256))
    annotated_image_key: Mapped[str | None] = mapped_column(String(256))
    cv_result: Mapped[dict | None] = mapped_column(JSONB)
    standard_gaps: Mapped[dict | None] = mapped_column(JSONB)
    analysis_report: Mapped[dict | None] = mapped_column(JSONB)
    report_file_key: Mapped[str | None] = mapped_column(String(256))
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewed_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    review_comment: Mapped[str | None] = mapped_column(Text)
    created_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = (Index("idx_conversation_user", "user_id", "last_active_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    title: Mapped[str | None] = mapped_column(String(128))
    message_count: Mapped[int] = mapped_column(Integer, default=0)
    last_active_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class ReviewRequest(Base):
    """复核工单：pending 待复核 → done 已复核 / rejected 被驳回 → reapply 驳回重审 → done；
    special 特殊标注（可由处理人改写回合格/不合格后转 done）。"""
    __tablename__ = "review_requests"
    __table_args__ = (
        Index("idx_review_inspection", "inspection_id"),
        Index("idx_review_applicant", "applicant_id", "status"),
        Index("idx_review_status", "status"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    inspection_id: Mapped[int] = mapped_column(ForeignKey("inspection_logs.id"))
    applicant_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    source: Mapped[str] = mapped_column(String(16), default="operator_request")
    status: Mapped[str] = mapped_column(String(16), default="pending")
    reviewer_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str | None] = mapped_column(String(16))  # confirm_fail|confirm_pass|reject|special
    comment: Mapped[str | None] = mapped_column(Text)
    applicant_note: Mapped[str | None] = mapped_column(Text)
    force_reject: Mapped[bool] = mapped_column(Boolean, default=False)
    final_accepted: Mapped[bool | None] = mapped_column(Boolean)  # 被驳回后操作工"确认处理"=True
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reject_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reapply_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))


class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("idx_audit_user", "user_id", "created_at"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String(64))
    target_type: Mapped[str | None] = mapped_column(String(32))
    target_id: Mapped[str | None] = mapped_column(String(64))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=text("now()"))

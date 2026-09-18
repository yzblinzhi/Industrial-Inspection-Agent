"""初始化 6 张核心表

Revision ID: 0001
Revises:
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts():
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("password_hash", sa.String(128), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("display_name", sa.String(64), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "workpieces",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("workpiece_no", sa.String(64), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("material", sa.String(64), nullable=True),
        sa.Column("coating_spec", sa.String(128), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("workpiece_no"),
    )

    op.create_table(
        "quality_standards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("workpiece_id", sa.BigInteger(), sa.ForeignKey("workpieces.id", ondelete="CASCADE"), nullable=False),
        sa.Column("defect_type", sa.String(64), nullable=False),
        sa.Column("max_area_cm2", sa.Numeric(10, 2), nullable=True),
        sa.Column("max_count", sa.Integer(), nullable=True),
        sa.Column("max_dimension_mm", sa.Numeric(10, 2), nullable=True),
        sa.Column("confidence_threshold", sa.Numeric(4, 3), nullable=True),
        sa.Column("extra_rules", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("uq_std_workpiece_defect", "quality_standards", ["workpiece_id", "defect_type"], unique=True)

    op.create_table(
        "inspection_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("workpiece_id", sa.BigInteger(), sa.ForeignKey("workpieces.id"), nullable=True),
        sa.Column("workpiece_no", sa.String(64), nullable=False),
        sa.Column("batch_no", sa.String(64), nullable=True),
        sa.Column("image_key", sa.String(256), nullable=True),
        sa.Column("annotated_image_key", sa.String(256), nullable=True),
        sa.Column("cv_result", postgresql.JSONB(), nullable=True),
        sa.Column("standard_gaps", postgresql.JSONB(), nullable=True),
        sa.Column("analysis_report", postgresql.JSONB(), nullable=True),
        sa.Column("status", sa.String(16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reviewed_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_inspection_workpiece", "inspection_logs", ["workpiece_no", "created_at"])
    op.create_index("idx_inspection_batch", "inspection_logs", ["batch_no"])
    op.create_index("idx_inspection_session", "inspection_logs", ["session_id"])
    op.create_index("idx_inspection_status", "inspection_logs", ["status"])

    op.create_table(
        "conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(64), nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(128), nullable=True),
        sa.Column("message_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id"),
    )
    op.create_index("idx_conversation_user", "conversations", ["user_id", "last_active_at"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", sa.String(64), nullable=True),
        sa.Column("detail", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_audit_user", "audit_logs", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("conversations")
    op.drop_index("idx_inspection_status", table_name="inspection_logs")
    op.drop_index("idx_inspection_session", table_name="inspection_logs")
    op.drop_index("idx_inspection_batch", table_name="inspection_logs")
    op.drop_index("idx_inspection_workpiece", table_name="inspection_logs")
    op.drop_table("inspection_logs")
    op.drop_index("uq_std_workpiece_defect", table_name="quality_standards")
    op.drop_table("quality_standards")
    op.drop_table("workpieces")
    op.drop_table("users")

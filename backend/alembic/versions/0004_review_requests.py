"""复核工单化重构：新增 review_requests 表；inspection_logs 状态扩 special；
为历史 need_review 记录补建待复核工单

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "review_requests",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("inspection_id", sa.BigInteger(),
                  sa.ForeignKey("inspection_logs.id"), nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("source", sa.String(16), server_default=sa.text("'operator_request'"), nullable=False),
        sa.Column("status", sa.String(16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("decision", sa.String(16), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("applicant_note", sa.Text(), nullable=True),
        sa.Column("force_reject", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("final_accepted", sa.Boolean(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reject_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reapply_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_review_inspection", "review_requests", ["inspection_id"])
    op.create_index("idx_review_applicant", "review_requests", ["applicant_id", "status"])
    op.create_index("idx_review_status", "review_requests", ["status"])

    # 历史 need_review 记录补建待复核工单（保证工作台可见）
    op.execute(
        """
        INSERT INTO review_requests (inspection_id, applicant_id, source, status, created_at, updated_at)
        SELECT id, created_by, 'legacy', 'pending', now(), now()
        FROM inspection_logs
        WHERE status = 'need_review'
          AND NOT EXISTS (SELECT 1 FROM review_requests r WHERE r.inspection_id = inspection_logs.id)
        """
    )


def downgrade() -> None:
    op.drop_table("review_requests")

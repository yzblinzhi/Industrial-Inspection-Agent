"""inspection_logs 增加 report_file_key（归档报告在 MinIO 的 object key）

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-09
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "inspection_logs",
        sa.Column("report_file_key", sa.String(256), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("inspection_logs", "report_file_key")

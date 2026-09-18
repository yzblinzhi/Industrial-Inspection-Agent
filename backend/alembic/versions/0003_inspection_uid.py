"""inspection_logs 增加 inspection_uid：同一会话内每轮检测一条独立单据

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-10
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inspection_logs", sa.Column("inspection_uid", sa.String(64), nullable=True))
    # PostgreSQL 默认 NULLS DISTINCT：多行 NULL 不冲突，旧记录（无 uid）兼容
    op.create_index("uq_inspection_uid", "inspection_logs", ["inspection_uid"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_inspection_uid", table_name="inspection_logs")
    op.drop_column("inspection_logs", "inspection_uid")

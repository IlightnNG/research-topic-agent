"""chat_messages.trace_json（3.3：L3 工具轨迹可回放）

Revision ID: 0004_chat_trace
Revises: 0003_reports_sections
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_chat_trace"
down_revision = "0003_reports_sections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    if "trace_json" not in columns:
        op.add_column("chat_messages", sa.Column("trace_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_column("trace_json")

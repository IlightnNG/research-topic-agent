"""chat_messages.reason_code（3.1：拒答原因可本地化）

Revision ID: 0005_chat_reason
Revises: 0004_chat_trace
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_chat_reason"
down_revision = "0004_chat_trace"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("chat_messages")}
    if "reason_code" not in columns:
        op.add_column("chat_messages", sa.Column("reason_code", sa.String(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("chat_messages") as batch:
        batch.drop_column("reason_code")

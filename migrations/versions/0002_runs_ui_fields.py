"""runs UI fields (period / focus_hint / scope_sha)

Revision ID: 0002_runs_ui_fields
Revises: 0001_initial
Create Date: 2026-10-20

注意：`0001_initial` 用 `metadata.create_all` 建表，因此**新建库**里这些列已存在；
本迁移必须**幂等**（只在缺列时 ALTER），否则新库升级会报 duplicate column。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_runs_ui_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

_COLUMNS = ("period", "focus_hint", "scope_sha")


def _existing() -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {column["name"] for column in inspector.get_columns("runs")}


def upgrade() -> None:
    existing = _existing()
    with op.batch_alter_table("runs") as batch:
        for name in _COLUMNS:
            if name not in existing:
                batch.add_column(sa.Column(name, sa.String(), nullable=True))


def downgrade() -> None:
    existing = _existing()
    with op.batch_alter_table("runs") as batch:
        for name in reversed(_COLUMNS):
            if name in existing:
                batch.drop_column(name)

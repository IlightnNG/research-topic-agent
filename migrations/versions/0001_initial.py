"""initial schema: 24 tables (12 revised + 12 new) — ADR-0005 §3

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-19

实现取舍（**必须知道**）：
本迁移直接调用 `metadata.create_all()`，而不是逐表手写 `op.create_table`。
理由：`db/tables.py` 是 DDL 的唯一来源，手写一份迁移等于把同一份 DDL 维护两遍，
必然漂移（Phase 0 的静默错误 #1 就是 schema 与代码不同步）。
代价：后续**增量**迁移仍需手写/autogenerate（`alembic revision --autogenerate`），
`create_all` 只用于这个初始版本。
"""

from __future__ import annotations

from alembic import op

import lit_agent.db.tables  # noqa: F401  (注册全部表到 metadata)
from lit_agent.db.base import metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    metadata.drop_all(bind=op.get_bind(), checkfirst=True)

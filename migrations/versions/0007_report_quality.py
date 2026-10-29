"""report quality metadata: fallback_count, coverage (3.3 / S7)

Revision ID: 0007_report_quality
Revises: 0006_report_v2
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_report_quality"
down_revision = "0006_report_v2"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _columns("reports")
    if "fallback_count" not in existing:
        op.add_column("reports", sa.Column("fallback_count", sa.Integer(), nullable=True))
    if "coverage" not in existing:
        op.add_column("reports", sa.Column("coverage", sa.Float(), nullable=True))


def downgrade() -> None:
    existing = _columns("reports")
    with op.batch_alter_table("reports") as batch:
        if "fallback_count" in existing:
            batch.drop_column("fallback_count")
        if "coverage" in existing:
            batch.drop_column("coverage")

"""report thin flag (3.3 / S8)

Revision ID: 0008_report_thin
Revises: 0007_report_quality
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_report_thin"
down_revision = "0007_report_quality"
branch_labels = None
depends_on = None


def upgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reports")}
    if "thin" not in existing:
        op.add_column("reports", sa.Column("thin", sa.Integer(), nullable=True))


def downgrade() -> None:
    existing = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("reports")}
    if "thin" in existing:
        with op.batch_alter_table("reports") as batch:
            batch.drop_column("thin")

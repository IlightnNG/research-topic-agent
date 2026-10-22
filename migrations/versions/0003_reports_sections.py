"""reports.sections_json（S12：真实分节）

Revision ID: 0003_reports_sections
Revises: 0002_runs_ui_fields
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_reports_sections"
down_revision = "0002_runs_ui_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("reports")}
    if "sections_json" not in columns:
        op.add_column("reports", sa.Column("sections_json", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("reports") as batch:
        batch.drop_column("sections_json")

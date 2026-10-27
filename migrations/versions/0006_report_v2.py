"""report v2：paper_cards / report_steps / 报告元信息 / PDF 字段（3.2 S1）

Revision ID: 0006_report_v2
Revises: 0005_chat_reason
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_report_v2"
down_revision = "0005_chat_reason"
branch_labels = None
depends_on = None


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    reports = _columns("reports")
    for name, column in (
        ("language", sa.Column("language", sa.String(), nullable=True)),
        ("generated_by", sa.Column("generated_by", sa.String(), nullable=True)),
        ("word_count", sa.Column("word_count", sa.Integer(), nullable=True)),
        ("fallback_reason", sa.Column("fallback_reason", sa.Text(), nullable=True)),
    ):
        if name not in reports:
            op.add_column("reports", column)

    runs = _columns("runs")
    if "report_language" not in runs:
        op.add_column("runs", sa.Column("report_language", sa.String(), nullable=True))

    papers = _columns("papers")
    for name, column in (
        ("pdf_path", sa.Column("pdf_path", sa.String(), nullable=True)),
        ("pdf_url", sa.Column("pdf_url", sa.String(), nullable=True)),
        ("full_text_status", sa.Column("full_text_status", sa.String(), nullable=True)),
    ):
        if name not in papers:
            op.add_column("papers", column)

    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "paper_cards" not in inspector.get_table_names():
        op.create_table(
            "paper_cards",
            sa.Column("paper_id", sa.String(), primary_key=True),
            sa.Column("content_sha", sa.String(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("card_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.String(), nullable=False),
        )

    if "report_steps" not in inspector.get_table_names():
        op.create_table(
            "report_steps",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("run_id", sa.String(), nullable=True),
            sa.Column("report_id", sa.String(), nullable=True),
            sa.Column("step", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("duration_ms", sa.Integer(), nullable=True),
            sa.Column("tokens", sa.Integer(), nullable=True),
            sa.Column("cost_usd", sa.Float(), nullable=True),
            sa.Column("error_code", sa.String(), nullable=True),
            sa.Column("meta_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.String(), nullable=False),
        )
        op.create_index("ix_report_steps_run", "report_steps", ["run_id"])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "report_steps" in inspector.get_table_names():
        op.drop_table("report_steps")
    if "paper_cards" in inspector.get_table_names():
        op.drop_table("paper_cards")

    for table in ("reports", "runs", "papers"):
        existing = _columns(table)
        for name in ("language", "generated_by", "word_count", "fallback_reason"):
            if table == "reports" and name in existing:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)
        for name in ("report_language",):
            if table == "runs" and name in existing:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)
        for name in ("pdf_path", "pdf_url", "full_text_status"):
            if table == "papers" and name in existing:
                with op.batch_alter_table(table) as batch:
                    batch.drop_column(name)

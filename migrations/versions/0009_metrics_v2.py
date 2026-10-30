"""metric definitions/points/spans/experiments (3.4 / S16)

Revision ID: 0009_metrics_v2
Revises: 0008_report_thin
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0009_metrics_v2"
down_revision = "0008_report_thin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    if "metric_definitions" not in names:
        op.create_table(
            "metric_definitions",
            sa.Column("metric_id", sa.String(), primary_key=True),
            sa.Column("version", sa.String(), nullable=False),
            sa.Column("domain", sa.String(), nullable=False),
            sa.Column("unit", sa.String(), nullable=False),
            sa.Column("direction", sa.String(), nullable=False),
            sa.Column("formula", sa.Text(), nullable=False),
            sa.Column("target_json", sa.Text()),
            sa.Column("owner", sa.String()),
            sa.Column("created_at", sa.String(), nullable=False),
        )
    if "metric_points" not in names:
        op.create_table(
            "metric_points",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("metric_id", sa.String(), nullable=False),
            sa.Column("metric_version", sa.String(), nullable=False),
            sa.Column("scope", sa.String(), nullable=False),
            sa.Column("scope_id", sa.String(), nullable=False),
            sa.Column("run_id", sa.String()),
            sa.Column("node_id", sa.String()),
            sa.Column("step", sa.String()),
            sa.Column("value", sa.Float()),
            sa.Column("numerator", sa.Float()),
            sa.Column("denominator", sa.Float()),
            sa.Column("sample_size", sa.Integer()),
            sa.Column("unit", sa.String()),
            sa.Column("config_hash", sa.String()),
            sa.Column("prompt_version", sa.String()),
            sa.Column("model", sa.String()),
            sa.Column("dataset", sa.String()),
            sa.Column("ts", sa.String(), nullable=False),
        )
        op.create_index("ix_metric_points_run", "metric_points", ["run_id"])
        op.create_index("ix_metric_points_metric", "metric_points", ["metric_id"])
    if "run_spans" not in names:
        op.create_table(
            "run_spans",
            sa.Column("span_id", sa.String(), primary_key=True),
            sa.Column("trace_id", sa.String(), nullable=False),
            sa.Column("parent_span_id", sa.String()),
            sa.Column("run_id", sa.String(), nullable=False),
            sa.Column("node_id", sa.String()),
            sa.Column("step", sa.String()),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("start_ts", sa.String(), nullable=False),
            sa.Column("end_ts", sa.String()),
            sa.Column("duration_ms", sa.Integer()),
            sa.Column("attributes_json", sa.Text()),
            sa.Column("error_code", sa.String()),
        )
        op.create_index("ix_run_spans_run", "run_spans", ["run_id"])
    if "experiments" not in names:
        op.create_table(
            "experiments",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("name", sa.String(), nullable=False),
            sa.Column("hypothesis", sa.Text()),
            sa.Column("config_json", sa.Text(), nullable=False),
            sa.Column("config_hash", sa.String(), nullable=False),
            sa.Column("dataset", sa.String()),
            sa.Column("baseline_run_id", sa.String()),
            sa.Column("candidates_json", sa.Text()),
            sa.Column("score", sa.Float()),
            sa.Column("hard_fail_json", sa.Text()),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column("created_at", sa.String(), nullable=False),
        )


def downgrade() -> None:
    bind = op.get_bind()
    names = set(sa.inspect(bind).get_table_names())
    for table in ("experiments", "run_spans", "metric_points", "metric_definitions"):
        if table in names:
            op.drop_table(table)

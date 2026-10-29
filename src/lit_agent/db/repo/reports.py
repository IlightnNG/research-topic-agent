"""报告仓储：`(run_id, content_sha)` 幂等；内容不同必须新增行（漂移是证据，不许覆盖）。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_reports
from lit_agent.models.report import Report

__all__ = ["count", "get_by_run", "insert_ignore", "latest_by_topic", "list_by_topic"]


def insert_ignore(conn: Connection, report: Report, *, now: str | None = None) -> int:
    """幂等写入：同 run 同内容 → 0（已存在）；内容变化 → 1（新增一行，需另行记 report_drift 事件）。"""
    stmt = (
        sqlite_insert(t_reports)
        .values(
            report_id=report.report_id,
            topic_id=report.topic_id,
            run_id=report.run_id,
            period=report.period,
            title=report.title,
            content_md=report.content_md,
            content_sha=report.content_sha,
            claims_json=json.dumps(
                [claim.model_dump(mode="json") for claim in report.claims], ensure_ascii=False
            ),
            sections_json=json.dumps(
                [section.model_dump(mode="json") for section in report.sections],
                ensure_ascii=False,
            )
            if report.sections
            else None,
            metrics_snapshot_json=json.dumps(
                report.metrics_snapshot, ensure_ascii=False, default=str
            ),
            n_claims=report.n_claims or len(report.claims),
            degraded=int(report.degraded),
            language=report.language,
            generated_by=report.generated_by,
            fallback_count=report.fallback_count,
            coverage=report.coverage,
            word_count=report.word_count,
            fallback_reason=report.fallback_reason,
            created_at=now or utcnow_iso(),
        )
        .on_conflict_do_nothing(index_elements=[t_reports.c.run_id, t_reports.c.content_sha])
    )
    result = conn.execute(stmt)
    return int(result.rowcount or 0)


def get_by_run(conn: Connection, run_id: str) -> Sequence[Any]:
    stmt = select(t_reports).where(t_reports.c.run_id == run_id).order_by(t_reports.c.created_at)
    return conn.execute(stmt).all()


def list_by_topic(conn: Connection, topic_id: str, *, limit: int = 20) -> Sequence[Any]:
    stmt = (
        select(t_reports)
        .where(t_reports.c.topic_id == topic_id)
        .order_by(t_reports.c.created_at.desc())
        .limit(limit)
    )
    return conn.execute(stmt).all()


def latest_by_topic(conn: Connection, topic_id: str) -> Any:
    return conn.execute(
        select(t_reports)
        .where(t_reports.c.topic_id == topic_id)
        .order_by(t_reports.c.created_at.desc())
        .limit(1)
    ).first()


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_reports)).scalar_one())

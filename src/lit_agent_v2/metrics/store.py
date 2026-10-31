"""Metric and span persistence for v2."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.storage.db import Database

__all__ = ["MetricStore"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


class MetricStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def point(
        self,
        metric_id: str,
        value: float | None,
        *,
        version: str = "1.0",
        run_id: str | None = None,
        node_id: str | None = None,
        step: str | None = None,
        numerator: float | None = None,
        denominator: float | None = None,
        sample_size: int | None = None,
        **extra: Any,
    ) -> None:
        if denominator == 0:
            value = None
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO metric_points"
                "(id,metric_id,version,run_id,node_id,step,value,numerator,denominator,"
                "sample_size,config_hash,model,prompt_version,dataset,ts)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    metric_id,
                    version,
                    run_id,
                    node_id,
                    step,
                    value,
                    numerator,
                    denominator,
                    sample_size,
                    extra.get("config_hash"),
                    extra.get("model"),
                    extra.get("prompt_version"),
                    extra.get("dataset"),
                    _now(),
                ),
            )

    def points(self, run_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT metric_id,value,numerator,denominator,sample_size,ts"
                " FROM metric_points WHERE run_id=? ORDER BY ts, metric_id",
                (run_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def span(
        self,
        run_id: str,
        name: str,
        *,
        node_id: str | None = None,
        step: str | None = None,
        status: str = "ok",
        duration_ms: int = 0,
        attributes: dict[str, Any] | None = None,
    ) -> str:
        span_id = uuid.uuid4().hex
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO run_spans"
                "(span_id,run_id,node_id,step,name,status,start_ts,end_ts,duration_ms,"
                "attributes_json,error_code) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (
                    span_id,
                    run_id,
                    node_id,
                    step,
                    name,
                    status,
                    _now(),
                    _now(),
                    duration_ms,
                    json.dumps(attributes or {}, ensure_ascii=False),
                    None,
                ),
            )
        return span_id

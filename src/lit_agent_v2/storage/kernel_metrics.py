"""Persistent kernel metrics backed by SQLite."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.kernel.agent.task import KernelResult
from lit_agent_v2.storage.db import Database

__all__ = ["KernelMetricStore"]


class KernelMetricStore:
    def __init__(self, db: Database) -> None:
        self.db = db

    def record(
        self,
        result: KernelResult,
        *,
        task_id: str,
        model: str = "",
        schema_ok: bool = True,
        latency_ms: float = 0.0,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        metric_id = uuid.uuid4().hex
        metrics = result.metrics
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO kernel_metrics"
                "(id,task_id,model,success,stop_reason,error_code,steps,tool_calls,"
                "tool_errors,repairs,compactions,prompt_tokens,completion_tokens,"
                "cost_usd,latency_ms,schema_ok,metadata_json,created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    metric_id,
                    task_id,
                    model,
                    int(result.stop_reason == "final"),
                    result.stop_reason,
                    result.error_code,
                    int(metrics.get("steps", 0)),
                    int(metrics.get("tool_calls", 0)),
                    int(metrics.get("tool_errors", 0)),
                    int(metrics.get("repairs", 0)),
                    int(metrics.get("compactions", 0)),
                    int(result.usage.get("prompt_tokens", 0)),
                    int(result.usage.get("completion_tokens", 0)),
                    float(result.cost_usd),
                    float(latency_ms),
                    int(schema_ok),
                    json.dumps(metadata or {}, ensure_ascii=False),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return metric_id

    def summary(self) -> dict[str, Any]:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n,"
                " SUM(success) AS successes,"
                " SUM(schema_ok) AS schema_ok,"
                " AVG(steps) AS steps,"
                " AVG(tool_calls) AS tool_calls,"
                " AVG(tool_errors) AS tool_errors,"
                " AVG(repairs) AS repairs,"
                " AVG(compactions) AS compactions,"
                " AVG(prompt_tokens) AS prompt_tokens,"
                " AVG(completion_tokens) AS completion_tokens,"
                " SUM(cost_usd) AS cost_usd,"
                " AVG(latency_ms) AS latency_ms"
                " FROM kernel_metrics"
            ).fetchone()
        return dict(row) if row else {}

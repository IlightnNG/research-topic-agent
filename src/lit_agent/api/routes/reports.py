"""报告历史（按 topic）。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine
from lit_agent.db.session import connect

router = APIRouter()


@router.get("/{topic_id}/reports")
def list_reports(
    topic_id: str,
    limit: int = Query(default=20, ge=1, le=200),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = conn.execute(
            text(
                "SELECT report_id, run_id, period, title, content_sha, n_claims, degraded, created_at"
                " FROM reports WHERE topic_id = :t ORDER BY created_at DESC LIMIT :limit"
            ),
            {"t": topic_id, "limit": limit},
        ).all()
    items = [
        {
            "report_id": row[0],
            "run_id": row[1],
            "period": row[2],
            "title": row[3],
            "content_sha": row[4],
            "n_claims": row[5],
            "degraded": bool(row[6]),
            "created_at": row[7],
        }
        for row in rows
    ]
    return {"topic_id": topic_id, "items": items, "count": len(items)}


@router.get("/{topic_id}/reports/{report_id}")
def get_report(topic_id: str, report_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    from lit_agent.errors import E_CONFIG_INVALID, LitError

    with connect(engine) as conn:
        row = conn.execute(
            text("SELECT * FROM reports WHERE topic_id = :t AND report_id = :r"),
            {"t": topic_id, "r": report_id},
        ).first()
    if row is None:
        raise LitError(
            E_CONFIG_INVALID, f"报告不存在：{report_id}", context={"report_id": report_id}
        )
    data = dict(row._mapping)
    data["claims"] = json.loads(data.pop("claims_json", "null") or "[]")
    data.pop("metrics_snapshot_json", None)
    return data

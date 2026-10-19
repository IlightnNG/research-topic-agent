"""Run 详情 / 事件分页 / 报告 / SSE 流。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.api.sse import event_stream
from lit_agent.config import Settings
from lit_agent.db.repo import reports as report_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_CONFIG_INVALID, LitError

router = APIRouter()


def _require(value: Any, label: str) -> Any:
    if value is None:
        raise LitError(E_CONFIG_INVALID, f"{label} 不存在", context={"missing": label})
    return value


@router.get("/{run_id}")
def get_run(run_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        row = _require(
            conn.execute(text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}).first(),
            f"run {run_id}",
        )
    data = dict(row._mapping)
    data.pop("config_snapshot_json", None)
    return data


@router.get("/{run_id}/events")
def list_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = conn.execute(
            text(
                "SELECT seq, ts, type, stage, agent, severity, dedupe_key, payload_json"
                " FROM run_events WHERE run_id = :rid AND seq > :after ORDER BY seq LIMIT :limit"
            ),
            {"rid": run_id, "after": after_seq, "limit": limit},
        ).all()
    items = [
        {
            "seq": row[0],
            "ts": row[1],
            "type": row[2],
            "stage": row[3],
            "agent": row[4],
            "severity": row[5],
            "dedupe_key": row[6],
            "payload": json.loads(row[7] or "{}"),
        }
        for row in rows
    ]
    return {"run_id": run_id, "after_seq": after_seq, "items": items, "count": len(items)}


@router.get("/{run_id}/report")
def get_report(run_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = report_repo.get_by_run(conn, run_id)
    if not rows:
        raise LitError(E_CONFIG_INVALID, f"run {run_id} 尚无报告", context={"run_id": run_id})
    row = rows[-1]
    data = dict(row._mapping)
    data["claims"] = json.loads(data.pop("claims_json", "null") or "[]")
    data.pop("metrics_snapshot_json", None)
    return data


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    request: Request,
    after_seq: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    header_seq = request.headers.get("last-event-id")
    start = int(header_seq) if header_seq and header_seq.isdigit() else after_seq
    return StreamingResponse(
        event_stream(settings, run_id, after_seq=start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )

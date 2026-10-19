"""SSE：**从 SQLite 补发**（真相源在库），流式帧不进事件表。

语义
- `after_seq` 或 `Last-Event-ID` 指定起点；先补发历史，再轮询新事件；
- run 进入终态（succeeded/failed/aborted）后发 `event: end` 关闭；
- 每 15 s 发一次 `event: heartbeat`（测试可把 `idle_timeout_s` 调小）。
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine

__all__ = ["event_stream"]

_TERMINAL = {"succeeded", "failed", "aborted"}


def _fetch(engine: object, run_id: str, after_seq: int, limit: int) -> list[dict]:
    from lit_agent.db.session import connect as _connect

    with _connect(engine) as conn:  # type: ignore[arg-type]
        rows = conn.execute(
            text(
                "SELECT seq, ts, type, stage, severity, payload_json FROM run_events"
                " WHERE run_id = :rid AND seq > :after ORDER BY seq LIMIT :limit"
            ),
            {"rid": run_id, "after": after_seq, "limit": limit},
        ).all()
    return [
        {
            "seq": row[0],
            "ts": row[1],
            "type": row[2],
            "stage": row[3],
            "severity": row[4],
            "payload": json.loads(row[5] or "{}"),
        }
        for row in rows
    ]


def _run_state(engine: object, run_id: str) -> str | None:
    with connect(engine) as conn:  # type: ignore[arg-type]
        value = conn.execute(
            text("SELECT state FROM runs WHERE id = :rid"), {"rid": run_id}
        ).scalar_one_or_none()
    return str(value) if value else None


async def event_stream(
    settings: Settings,
    run_id: str,
    *,
    after_seq: int = 0,
    poll_s: float = 0.2,
    idle_timeout_s: float = 10.0,
    heartbeat_s: float = 15.0,
) -> AsyncIterator[str]:
    engine = make_engine(settings)
    cursor = after_seq
    last_beat = time.monotonic()
    start = last_beat
    try:
        while True:
            events = _fetch(engine, run_id, cursor, 200)
            for event in events:
                cursor = int(event["seq"])
                yield f"id: {cursor}\nevent: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
                last_beat = time.monotonic()

            state = _run_state(engine, run_id)
            if state in _TERMINAL and not _fetch(engine, run_id, cursor, 1):
                yield f"event: end\ndata: {json.dumps({'state': state, 'last_seq': cursor})}\n\n"
                return

            now = time.monotonic()
            if heartbeat_s and now - last_beat >= heartbeat_s:
                yield "event: heartbeat\ndata: {}\n\n"
                last_beat = now
            if idle_timeout_s and now - start >= idle_timeout_s:
                yield f"event: end\ndata: {json.dumps({'state': state, 'last_seq': cursor})}\n\n"
                return
            await asyncio.sleep(poll_s)
    finally:
        engine.dispose()

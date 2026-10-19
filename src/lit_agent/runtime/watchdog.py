"""看门狗：检测"长时间没有新事件"的 run（guide §13，Phase 1 只做检测与留痕）。

主动取消留 Phase 2（P2-WATCH-01）：Python 线程无法被强杀，Phase 1 只发 `guard_trigger`
事件让上层（人或调度）决定，避免"假装取消了"。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.base import parse_iso
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_GUARD_TIMEOUT
from lit_agent.models._base import Severity
from lit_agent.models.event import EventType
from lit_agent.runtime.events import SqliteEventLog

__all__ = ["last_event_ts", "scan"]


def last_event_ts(settings: Settings, run_id: str) -> datetime | None:
    active = make_engine(settings)
    try:
        with connect(active) as conn:
            value = conn.execute(
                text("SELECT MAX(ts) FROM run_events WHERE run_id = :rid"), {"rid": run_id}
            ).scalar_one_or_none()
    finally:
        active.dispose()
    return parse_iso(str(value)) if value else None


def scan(
    settings: Settings,
    run_id: str,
    *,
    stale_seconds: float = 300.0,
    now: datetime | None = None,
) -> dict[str, Any]:
    """返回 `{stale, idle_s}`；超时则写一条 `guard_trigger` 事件。"""
    reference = now or datetime.now(UTC)
    last = last_event_ts(settings, run_id)
    idle_s = (reference - last).total_seconds() if last else float("inf")
    stale = idle_s >= stale_seconds
    if stale:
        active = make_engine(settings)
        try:
            SqliteEventLog(active, run_id).emit(
                EventType.GUARD_TRIGGER,
                stage="watchdog",
                agent="watchdog",
                severity=Severity.WARNING,
                payload={
                    "code": E_GUARD_TIMEOUT,
                    "guard": "G10_timeout",
                    "idle_s": None if idle_s == float("inf") else round(idle_s, 1),
                    "stale_seconds": stale_seconds,
                },
            )
        finally:
            active.dispose()
    return {"stale": stale, "idle_s": None if idle_s == float("inf") else round(idle_s, 1)}

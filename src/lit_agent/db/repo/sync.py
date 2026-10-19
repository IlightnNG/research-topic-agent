"""同步水位线仓储（`sync_state`）：增量抓取的游标与最近成功时间。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_sync_state

__all__ = ["get", "list_all", "set_cursor", "set_error"]


def get(conn: Connection, source: str, selector: str) -> Any:
    stmt = select(t_sync_state).where(
        t_sync_state.c.source == source, t_sync_state.c.selector == selector
    )
    return conn.execute(stmt).first()


def set_cursor(
    conn: Connection,
    source: str,
    selector: str,
    *,
    cursor: str | None = None,
    since: str | None = None,
    status: str = "idle",
    error_code: str | None = None,
    now: str | None = None,
) -> None:
    """写入/更新水位线（**不允许回退**：只在新值非空时覆盖）。"""
    stamp = now or utcnow_iso()
    stmt = sqlite_insert(t_sync_state).values(
        source=source,
        selector=selector,
        last_cursor=cursor,
        last_since=since,
        last_success_at=stamp if status == "idle" else None,
        status=status,
        error_code=error_code,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=[t_sync_state.c.source, t_sync_state.c.selector],
        set_={
            "last_cursor": stmt.excluded.last_cursor,
            "last_since": stmt.excluded.last_since,
            "last_success_at": stmt.excluded.last_success_at,
            "status": stmt.excluded.status,
            "error_code": stmt.excluded.error_code,
        },
    )
    conn.execute(stmt)


def set_error(
    conn: Connection, source: str, selector: str, error_code: str, *, now: str | None = None
) -> None:
    conn.execute(
        t_sync_state.update()
        .where(t_sync_state.c.source == source, t_sync_state.c.selector == selector)
        .values(status="error", error_code=error_code)
    )


def list_all(conn: Connection) -> Sequence[Any]:
    return conn.execute(select(t_sync_state).order_by(t_sync_state.c.source)).all()

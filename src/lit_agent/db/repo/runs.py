"""运行（run）仓储：状态机、事件序号分配、幂等命中计数。

**seq 分配是本文件的核心**（ADR-0005 §5）：
`UPDATE runs SET next_seq = next_seq + 1 WHERE id = :id RETURNING next_seq`
—— 单条语句完成"取号"，在同一事务内不会与其它写者抢到同一个值；
禁止 `MAX(seq)+1`（读-写之间有竞态）与 Python 侧计数器（崩溃即丢失）。
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.engine import Connection

from lit_agent.db.base import utcnow_iso
from lit_agent.db.tables import t_runs
from lit_agent.errors import E_UNEXPECTED, LitError
from lit_agent.models.run import RunState

__all__ = [
    "TERMINAL_STATES",
    "active",
    "allocate_seq",
    "bump_dup",
    "count",
    "create",
    "get",
    "list_by_topic",
    "set_stage",
    "set_state",
]

TERMINAL_STATES: frozenset[str] = frozenset(
    {RunState.SUCCEEDED.value, RunState.FAILED.value, RunState.ABORTED.value}
)

_ALLOCATE = text("UPDATE runs SET next_seq = next_seq + 1 WHERE id = :run_id RETURNING next_seq")


def create(
    conn: Connection,
    *,
    run_id: str,
    topic_id: str,
    trigger: str,
    config_snapshot: dict[str, Any] | None = None,
    input_hash: str = "",
    app_version: str = "",
    state: RunState = RunState.PENDING,
    now: str | None = None,
) -> None:
    stamp = now or utcnow_iso()
    conn.execute(
        t_runs.insert().values(
            id=run_id,
            topic_id=topic_id,
            trigger=trigger,
            state=state.value,
            config_snapshot_json=json.dumps(config_snapshot or {}, ensure_ascii=False, default=str),
            input_hash=input_hash,
            app_version=app_version,
            created_at=stamp,
            started_at=stamp if state is RunState.RUNNING else None,
        )
    )


def get(conn: Connection, run_id: str) -> Any:
    return conn.execute(select(t_runs).where(t_runs.c.id == run_id)).first()


def allocate_seq(conn: Connection, run_id: str) -> int:
    """取下一个事件序号（事务内原子自增）。"""
    row = conn.execute(_ALLOCATE, {"run_id": run_id}).first()
    if row is None:
        raise LitError(
            E_UNEXPECTED,
            f"run 不存在，无法分配事件序号：{run_id}",
            context={"run_id": run_id},
        )
    return int(row[0])


def bump_dup(conn: Connection, run_id: str) -> None:
    """幂等命中计数 +1（不产生事件，避免"去重事件被去重"）。"""
    conn.execute(
        text("UPDATE runs SET dup_events = dup_events + 1 WHERE id = :run_id"),
        {"run_id": run_id},
    )


def set_state(
    conn: Connection,
    run_id: str,
    state: RunState | str,
    *,
    error_code: str | None = None,
    now: str | None = None,
) -> None:
    value = state.value if isinstance(state, RunState) else str(state)
    stamp = now or utcnow_iso()
    values: dict[str, Any] = {"state": value, "error_code": error_code}
    if value == RunState.RUNNING.value:
        values["started_at"] = stamp
    if value in TERMINAL_STATES:
        values["finished_at"] = stamp
    conn.execute(t_runs.update().where(t_runs.c.id == run_id).values(**values))


def set_stage(conn: Connection, run_id: str, stage: str, *, completed: bool = False) -> None:
    values: dict[str, Any] = {"stage": stage}
    if completed:
        values["last_ok_stage"] = stage
    conn.execute(t_runs.update().where(t_runs.c.id == run_id).values(**values))


def list_by_topic(conn: Connection, topic_id: str, *, limit: int = 20) -> Sequence[Any]:
    stmt = (
        select(t_runs)
        .where(t_runs.c.topic_id == topic_id)
        .order_by(t_runs.c.created_at.desc())
        .limit(limit)
    )
    return conn.execute(stmt).all()


def active(conn: Connection, topic_id: str) -> Any:
    """当前 running 的 run（DB 层 `ux_runs_one_running` 保证最多一个）。"""
    stmt = select(t_runs).where(
        t_runs.c.topic_id == topic_id, t_runs.c.state == RunState.RUNNING.value
    )
    return conn.execute(stmt).first()


def count(conn: Connection) -> int:
    return int(conn.execute(select(func.count()).select_from(t_runs)).scalar_one())

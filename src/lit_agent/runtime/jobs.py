"""run 生命周期：锁、状态流转、孤儿清理、失败报告（guide §13）。"""

from __future__ import annotations

import os
import socket
from typing import Any

from sqlalchemy import select, text

from lit_agent.config import Settings
from lit_agent.db.repo import locks as lock_repo
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.db.tables import t_job_locks, t_runs
from lit_agent.errors import E_LOCK_HELD, E_UNEXPECTED, LitError
from lit_agent.models.run import RunState

__all__ = [
    "cleanup_orphans",
    "failure_report",
    "finish",
    "owner_token",
    "start",
]


def owner_token(run_id: str) -> str:
    return f"{socket.gethostname()}:{os.getpid()}:{run_id}"


def start(
    settings: Settings,
    topic_id: str,
    *,
    run_id: str,
    trigger: str = "manual",
    config_snapshot: dict[str, Any] | None = None,
    input_hash: str = "",
    engine: Any | None = None,
) -> str:
    """拿锁 + 建 run。已被占用 → `E_LOCK_HELD`（API 映射 409）。"""
    owned = engine is None
    active = engine or make_engine(settings)
    try:
        with connect(active, immediate=True) as conn:
            if not lock_repo.acquire(conn, topic_id, owner_token(run_id)):
                holder = lock_repo.get(conn, topic_id)
                raise LitError(
                    E_LOCK_HELD,
                    f"topic {topic_id} 已有运行中的 run",
                    context={
                        "topic_id": topic_id,
                        "owner": dict(holder._mapping).get("owner") if holder else None,
                    },
                )
            existing = run_repo.get(conn, run_id)
            if existing is not None:
                raise LitError(E_UNEXPECTED, f"run_id 已存在：{run_id}", context={"run_id": run_id})
            run_repo.create(
                conn,
                run_id=run_id,
                topic_id=topic_id,
                trigger=trigger,
                config_snapshot=config_snapshot,
                input_hash=input_hash,
                app_version=settings.app_version,
                state=RunState.RUNNING,
            )
    finally:
        if owned:
            active.dispose()
    return run_id


def finish(
    settings: Settings,
    run_id: str,
    *,
    state: RunState,
    error_code: str | None = None,
    engine: Any | None = None,
) -> None:
    owned = engine is None
    active = engine or make_engine(settings)
    try:
        with connect(active, immediate=True) as conn:
            row = run_repo.get(conn, run_id)
            if row is None:
                return
            topic_id = str(row._mapping["topic_id"])
            run_repo.set_state(conn, run_id, state, error_code=error_code)
            lock_repo.release(conn, topic_id)
    finally:
        if owned:
            active.dispose()


def failure_report(settings: Settings, run_id: str, error: LitError) -> dict[str, Any]:
    """失败报告四要素：错误码 / 最后成功阶段 / 已产出内容 / 建议动作。"""
    active = make_engine(settings)
    try:
        with connect(active) as conn:
            row = run_repo.get(conn, run_id)
            mapping = dict(row._mapping) if row else {}
            produced = conn.execute(
                text(
                    "SELECT COUNT(*) FROM run_events WHERE run_id = :rid AND type = 'phase_change'"
                ),
                {"rid": run_id},
            ).scalar_one()
    finally:
        active.dispose()
    return {
        "run_id": run_id,
        "error_code": error.code,
        "stage": mapping.get("stage"),
        "last_ok_stage": mapping.get("last_ok_stage"),
        "produced_events": int(produced),
        "suggestion": error.action_taken,
        "message": error.message,
    }


def cleanup_orphans(settings: Settings) -> dict[str, Any]:
    """清理过期锁，并把"无锁却仍 running"的 run 标为 aborted(orphan)。"""
    active = make_engine(settings)
    aborted: list[str] = []
    try:
        with connect(active, immediate=True) as conn:
            expired = lock_repo.cleanup_expired(conn)
            held_topics = {
                str(row[0]) for row in conn.execute(select(t_job_locks.c.topic_id)).all()
            }
            running = conn.execute(
                select(t_runs.c.id, t_runs.c.topic_id).where(
                    t_runs.c.state == RunState.RUNNING.value
                )
            ).all()
            for run_id, topic_id in running:
                if str(topic_id) not in held_topics:
                    run_repo.set_state(conn, str(run_id), RunState.ABORTED, error_code="orphan")
                    aborted.append(str(run_id))
    finally:
        active.dispose()
    return {"expired_locks": len(expired), "aborted_runs": aborted}

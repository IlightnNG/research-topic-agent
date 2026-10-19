"""`job_locks` 仓储：一 topic 同时只允许一个 run。

设计：DB 层互斥（主键）+ 过期时间（孤儿锁自动回收）。内存锁在进程重启后失效，
所以"能不能跑"的最终裁判必须是这张表。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.engine import Connection

from lit_agent.db.base import parse_iso, utcnow_iso
from lit_agent.db.tables import t_job_locks

__all__ = ["DEFAULT_TTL_S", "acquire", "cleanup_expired", "get", "heartbeat", "release"]

DEFAULT_TTL_S = 180


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def acquire(
    conn: Connection,
    topic_id: str,
    owner: str,
    *,
    ttl_s: int = DEFAULT_TTL_S,
    now: str | None = None,
) -> bool:
    """尝试拿锁。返回 False = 已被他人持有（调用方映射为 `409 E_LOCK_HELD`）。"""
    stamp = now or utcnow_iso()
    reference = parse_iso(stamp) or datetime.now(UTC)
    cleanup_expired(conn, now=stamp)
    stmt = sqlite_insert(t_job_locks).values(
        topic_id=topic_id,
        owner=owner,
        acquired_at=stamp,
        heartbeat_at=stamp,
        expires_at=_iso(reference + timedelta(seconds=ttl_s)),
    )
    stmt = stmt.on_conflict_do_nothing(index_elements=[t_job_locks.c.topic_id])
    result = conn.execute(stmt)
    return int(result.rowcount or 0) == 1


def heartbeat(
    conn: Connection,
    topic_id: str,
    owner: str,
    *,
    ttl_s: int = DEFAULT_TTL_S,
    now: str | None = None,
) -> bool:
    """续约；owner 不匹配返回 False（说明锁已被别人接管）。"""
    stamp = now or utcnow_iso()
    reference = parse_iso(stamp) or datetime.now(UTC)
    result = conn.execute(
        t_job_locks.update()
        .where(t_job_locks.c.topic_id == topic_id, t_job_locks.c.owner == owner)
        .values(heartbeat_at=stamp, expires_at=_iso(reference + timedelta(seconds=ttl_s)))
    )
    return int(result.rowcount or 0) == 1


def release(conn: Connection, topic_id: str, owner: str | None = None) -> bool:
    stmt = delete(t_job_locks).where(t_job_locks.c.topic_id == topic_id)
    if owner is not None:
        stmt = stmt.where(t_job_locks.c.owner == owner)
    result = conn.execute(stmt)
    return int(result.rowcount or 0) == 1


def cleanup_expired(conn: Connection, *, now: str | None = None) -> list[str]:
    """删除已过期的锁（孤儿锁），返回被清理的 topic_id 列表。"""
    stamp = now or utcnow_iso()
    expired = [
        str(row[0])
        for row in conn.execute(
            select(t_job_locks.c.topic_id).where(t_job_locks.c.expires_at < stamp)
        ).all()
    ]
    if expired:
        conn.execute(delete(t_job_locks).where(t_job_locks.c.expires_at < stamp))
    return expired


def get(conn: Connection, topic_id: str) -> Any:
    return conn.execute(select(t_job_locks).where(t_job_locks.c.topic_id == topic_id)).first()

"""事件仓储（`run_events`）：低层读写，不含业务语义（业务入口在 `runtime/events.py`）。"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.engine import Connection

from lit_agent.db.base import parse_iso
from lit_agent.db.tables import t_run_events
from lit_agent.models._base import Severity
from lit_agent.models.event import Event, EventType

__all__ = [
    "count",
    "ensure_schema_version",
    "exists_dedupe",
    "insert",
    "max_seq",
    "read",
    "row_to_event",
]


def insert(conn: Connection, event: Event) -> None:
    """写入一行事件（调用方负责序号分配与事务边界）。"""
    conn.execute(
        t_run_events.insert().values(
            run_id=event.run_id,
            seq=event.seq,
            ts=event.ts.isoformat().replace("+00:00", "Z"),
            type=event.type.value,
            stage=event.stage,
            agent=event.agent,
            severity=event.severity.value,
            dedupe_key=event.dedupe_key,
            payload_json=json.dumps(event.payload, ensure_ascii=False, default=str),
            schema_version=event.schema_version,
        )
    )


def exists_dedupe(conn: Connection, run_id: str, dedupe_key: str) -> bool:
    """幂等键是否已存在。

    先查再取号（而不是先插入再捕获冲突）：冲突后再回滚已消耗的 seq 会留下空号，
    破坏"`seq == 1..N` 连续"这一出口标准（D5）。单写者模型（`job_locks`）下无竞态；
    唯一索引仍是最终兜底。
    """
    stmt = (
        select(t_run_events.c.id)
        .where(t_run_events.c.run_id == run_id, t_run_events.c.dedupe_key == dedupe_key)
        .limit(1)
    )
    return conn.execute(stmt).first() is not None


def read(
    conn: Connection, run_id: str, *, after_seq: int = 0, limit: int = 1000
) -> Sequence[Event]:
    """按 seq 升序读取（`after_seq` 用于分页/续传）。"""
    stmt = (
        select(t_run_events)
        .where(t_run_events.c.run_id == run_id, t_run_events.c.seq > after_seq)
        .order_by(t_run_events.c.seq)
        .limit(limit)
    )
    return [row_to_event(row) for row in conn.execute(stmt).all()]


def row_to_event(row: Any, *, run_id: str | None = None) -> Event:
    """行 → 契约模型（`payload_json` 反序列化、时间补时区、枚举校验）。"""
    mapping = row._mapping if hasattr(row, "_mapping") else row
    payload_raw = mapping["payload_json"]
    payload = json.loads(payload_raw) if payload_raw else {}
    ts = parse_iso(mapping["ts"])
    if ts is None:
        raise ValueError(f"事件 ts 非法：{mapping['ts']!r}")
    return Event(
        id=mapping["id"],
        run_id=str(mapping["run_id"]),
        seq=int(mapping["seq"]),
        ts=ts,
        type=EventType(mapping["type"]),
        stage=mapping["stage"],
        agent=mapping["agent"],
        severity=Severity(mapping["severity"]),
        dedupe_key=mapping["dedupe_key"],
        payload=payload,
        schema_version=mapping["schema_version"],
    )


def max_seq(conn: Connection, run_id: str) -> int:
    value = conn.execute(
        select(func.max(t_run_events.c.seq)).where(t_run_events.c.run_id == run_id)
    ).scalar_one_or_none()
    return int(value or 0)


def count(conn: Connection, run_id: str | None = None) -> int:
    stmt = select(func.count()).select_from(t_run_events)
    if run_id is not None:
        stmt = stmt.where(t_run_events.c.run_id == run_id)
    return int(conn.execute(stmt).scalar_one())


def ensure_schema_version(event: Event, *, expected: str = "1.0") -> None:
    """事件 schema 版本守卫（写库前调用；版本不符说明事件生产者与消费者不同步）。"""
    if event.schema_version != expected:
        raise ValueError(f"事件 schema_version={event.schema_version} != {expected}")

"""**事件唯一入口**（guide §2.2 + ADR-0005 §5–§6）。

纪律
1. **先落库，后广播**：SSE/前端只是通知，真相在 `run_events`；
2. **日志与事件同源**：一条事实 → 一条事件（本模块）+ 一条日志（`logging.log_event`），
   禁止业务代码用 `logger.info` 记录"事实"（Phase 0 静默错误 #5/#6 的根因）；
3. **序号不跳号**：幂等命中先查后取号（避免回滚已分配的 seq 留下空号）；
4. **未配置日志时只写事件**：测试/库调用不应因为日志未初始化而隐式落盘。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy.engine import Connection, Engine

from lit_agent.db import repo as _repo  # noqa: F401  (包级导入便于调试)
from lit_agent.db.repo import events as event_repo
from lit_agent.db.repo import runs as run_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_DATA_DUP, E_DATA_SEQ_CONFLICT, LitError
from lit_agent.models._base import Severity
from lit_agent.models.event import Event, EventType

__all__ = ["Broadcaster", "SqliteEventLog"]


class Broadcaster(Protocol):
    """事件广播接口（SSE hub / 测试桩）。实现方必须容忍慢消费者，不得反向影响写路径。"""

    def publish(self, event: Event) -> None: ...


class SqliteEventLog:
    """单个 run 的事件写入器。线程内使用；并发由 `job_locks` 保证单写者。"""

    def __init__(
        self,
        engine: Engine,
        run_id: str,
        *,
        broadcaster: Broadcaster | None = None,
        jsonl_dir: Path | str | None = None,
        on_commit: Callable[[Event], None] | None = None,
    ) -> None:
        self._engine = engine
        self._run_id = run_id
        self._broadcaster = broadcaster
        self._jsonl_dir = Path(jsonl_dir) if jsonl_dir is not None else None
        self._on_commit = on_commit

    # ------------------------------------------------------------------ #
    # 写
    # ------------------------------------------------------------------ #
    def emit(
        self,
        event_type: EventType,
        *,
        stage: str | None = None,
        agent: str | None = None,
        severity: Severity = Severity.INFO,
        dedupe_key: str | None = None,
        payload: dict[str, Any] | None = None,
        ts: datetime | None = None,
        conn: Connection | None = None,
    ) -> Event | None:
        """写一条事件。

        `conn` 非空时在**调用方事务内**写入（事实与事件同生共死），广播由调用方在 commit 后触发；
        `conn` 为空时自开事务，commit 后立即广播。
        """
        if conn is not None:
            return self._emit_in(
                conn,
                event_type,
                stage=stage,
                agent=agent,
                severity=severity,
                dedupe_key=dedupe_key,
                payload=payload,
                ts=ts,
            )
        with connect(self._engine, immediate=True) as own:
            event = self._emit_in(
                own,
                event_type,
                stage=stage,
                agent=agent,
                severity=severity,
                dedupe_key=dedupe_key,
                payload=payload,
                ts=ts,
            )
        self._after_commit(event)
        return event

    def _emit_in(
        self,
        conn: Connection,
        event_type: EventType,
        *,
        stage: str | None,
        agent: str | None,
        severity: Severity,
        dedupe_key: str | None,
        payload: dict[str, Any] | None,
        ts: datetime | None,
    ) -> Event | None:
        stamp = ts or datetime.now(UTC)
        body = dict(payload or {})

        if dedupe_key is not None and event_repo.exists_dedupe(conn, self._run_id, dedupe_key):
            run_repo.bump_dup(conn, self._run_id)
            dup_payload = {
                "code": E_DATA_DUP,
                "dedupe_key": dedupe_key,
                "dropped_type": event_type.value,
                "note": "idempotent replay ignored; counter runs.dup_events incremented",
            }
            # 注意：去重告警自身的 dedupe_key 必须为 None，否则会"去重事件被去重"。
            dup = self._insert(
                conn,
                EventType.ERROR,
                stage=stage,
                agent=agent,
                severity=Severity.WARNING,
                dedupe_key=None,
                payload=dup_payload,
                ts=stamp,
            )
            return dup

        return self._insert(
            conn,
            event_type,
            stage=stage,
            agent=agent,
            severity=severity,
            dedupe_key=dedupe_key,
            payload=body,
            ts=stamp,
        )

    def _insert(
        self,
        conn: Connection,
        event_type: EventType,
        *,
        stage: str | None,
        agent: str | None,
        severity: Severity,
        dedupe_key: str | None,
        payload: dict[str, Any],
        ts: datetime,
    ) -> Event:
        seq = run_repo.allocate_seq(conn, self._run_id)
        event = Event(
            run_id=self._run_id,
            seq=seq,
            ts=ts,
            type=event_type,
            stage=stage,
            agent=agent,
            severity=severity,
            dedupe_key=dedupe_key,
            payload=payload,
        )
        try:
            event_repo.insert(conn, event)
        except Exception as exc:  # 唯一约束兜底：理论上不可达（单写者）
            raise LitError(
                E_DATA_SEQ_CONFLICT,
                f"事件写入冲突（run={self._run_id} seq={seq}）：{exc}",
                context={"run_id": self._run_id, "seq": seq, "dedupe_key": dedupe_key},
            ) from None
        return event

    # ------------------------------------------------------------------ #
    # 提交后副作用
    # ------------------------------------------------------------------ #
    def _after_commit(self, event: Event | None) -> None:
        if event is None:
            return
        self._log(event)
        self._export(event)
        if self._broadcaster is not None:
            self._broadcaster.publish(event)
        if self._on_commit is not None:
            self._on_commit(event)

    def _log(self, event: Event) -> None:
        from lit_agent import logging as app_logging

        if not app_logging.is_configured():
            return
        fields: dict[str, Any] = {
            "run_id": event.run_id,
            "seq": event.seq,
            "event_seq": event.seq,
            "stage": event.stage,
            "agent": event.agent,
            "dedupe_key": event.dedupe_key,
            "payload": event.payload,
        }
        if event.type is EventType.ERROR:
            fields["error_code"] = str(event.payload.get("code") or "E_UNEXPECTED")
            fields["retryable"] = bool(event.payload.get("retryable", False))
            fields["action_taken"] = str(event.payload.get("action_taken", "none"))
        app_logging.log_event(
            event.severity,
            f"event.{event.type.value}",
            f"{event.type.value} seq={event.seq}",
            **{key: value for key, value in fields.items() if value is not None},
        )

    def _export(self, event: Event) -> None:
        if self._jsonl_dir is None:
            return
        self._jsonl_dir.mkdir(parents=True, exist_ok=True)
        path = self._jsonl_dir / f"{self._run_id}.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(event.to_json_line() + "\n")

    # ------------------------------------------------------------------ #
    # 读
    # ------------------------------------------------------------------ #
    def replay(self, *, after_seq: int = 0, limit: int = 1000) -> list[Event]:
        with connect(self._engine) as conn:
            return list(event_repo.read(conn, self._run_id, after_seq=after_seq, limit=limit))

    def count(self) -> int:
        with connect(self._engine) as conn:
            return event_repo.count(conn, self._run_id)

    def dump_jsonl(self, path: Path | str) -> int:
        """把整轮事件导出成 JSONL（回放/取证用），返回行数。"""
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        events = self.replay(limit=1_000_000)
        with target.open("w", encoding="utf-8") as handle:
            for event in events:
                handle.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
        return len(events)

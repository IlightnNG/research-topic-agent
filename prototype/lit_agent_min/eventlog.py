"""事件写入（Phase 0：append-only JSONL；Phase 1 迁移到 SQLite `run_events`）。

契约：`docs/implementation/implementation-guide.md` §2.2（字段与类型）；`models.Event` 是唯一形状定义。

设计要点
- **只追加**：任何事件写入后不得修改；`seq` 在单个 run 内单调递增，由本模块维护。
- **崩溃可见**：写入失败抛 `EventLogError`（绝不为性能静默丢事件）；可选 `fsync=True` 保证落盘。
- **安全追加**：单次 `write` + 换行 + flush，避免半行；进程内用锁保证并发下 seq 不重复。
- **可续写**：打开已存在的日志时，从该 run 的最大 `seq` 继续（重跑不会产生重复 seq）。
- **可替换**：`EventSink` 协议固定 `emit(...)` 形状，Phase 1 的 SQLite 实现直接替换；
  上层（steps / 未来的 graph 节点）只依赖协议，不依赖 JSONL。
- **不掩盖损坏**：读取时遇到非法行立即报错并给出行号，便于定位被截断/被改写的日志。
"""

from __future__ import annotations

import os
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from .models import Event, EventType, RunId, Severity

__all__ = ["EventLogError", "EventSink", "JsonlEventLog", "read_events"]


class EventLogError(RuntimeError):
    """事件写入/读取的可预期错误（含文件路径与原因，供 CLI 友好呈现）。"""


class EventSink(Protocol):
    """事件接收端协议：Phase 0 是 JSONL，Phase 1 是 SQLite，签名保持一致。"""

    def emit(
        self,
        type: EventType | str,
        *,
        stage: str | None = None,
        agent: str | None = None,
        severity: Severity = Severity.INFO,
        payload: dict[str, Any] | None = None,
    ) -> Event: ...

    def events(self, run_id: RunId | None = None) -> list[Event]: ...


class JsonlEventLog:
    """append-only JSONL 事件日志（一个 run 一个 sink 实例）。"""

    def __init__(
        self,
        path: str | Path,
        *,
        run_id: RunId,
        schema_version: str = "1.0",
        fsync: bool = False,
    ) -> None:
        self.path = Path(path).expanduser()
        self.run_id = run_id
        self.schema_version = schema_version
        self._fsync = fsync
        self._lock = threading.Lock()
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise EventLogError(f"无法创建日志目录：{self.path.parent}（{exc}）") from None
        self._seq = self._scan_last_seq()

    # -- 写入 ---------------------------------------------------------------- #
    def emit(
        self,
        type: EventType | str,
        *,
        stage: str | None = None,
        agent: str | None = None,
        severity: Severity = Severity.INFO,
        payload: dict[str, Any] | None = None,
        ts: datetime | None = None,
    ) -> Event:
        """构造并追加一条事件，返回落盘后的 `Event`（含分配的 seq）。"""
        with self._lock:
            try:
                event = Event(
                    run_id=self.run_id,
                    seq=self._seq + 1,
                    ts=ts or datetime.now(UTC),
                    type=type,  # type: ignore[arg-type]  # 由 Pydantic 校验成 EventType
                    stage=stage,
                    agent=agent,
                    severity=severity,
                    payload=payload or {},
                    schema_version=self.schema_version,
                )
            except ValidationError as exc:
                raise EventLogError(f"事件不符合契约：{_format_validation(exc)}") from None

            try:
                with self.path.open("a", encoding="utf-8", newline="\n") as handle:
                    handle.write(event.to_json_line() + "\n")
                    handle.flush()
                    if self._fsync:
                        os.fsync(handle.fileno())
            except OSError as exc:
                raise EventLogError(f"事件写入失败：{self.path}（{exc}）") from None

            self._seq = event.seq
            return event

    # -- 读取 ---------------------------------------------------------------- #
    def events(self, run_id: RunId | None = None) -> list[Event]:
        return read_events(self.path, run_id=run_id if run_id is not None else self.run_id)

    @property
    def seq(self) -> int:
        """当前已写入的最大 seq（0 表示还没写过）。"""
        return self._seq

    # -- 内部 ---------------------------------------------------------------- #
    def _scan_last_seq(self) -> int:
        if not self.path.exists():
            return 0
        last = 0
        for event in read_events(self.path, run_id=self.run_id):
            last = max(last, event.seq)
        return last


def read_events(path: str | Path, *, run_id: RunId | None = None) -> list[Event]:
    """读取事件日志（可按 run_id 过滤）；遇到非法行立即报错并指出行号。"""
    log_path = Path(path).expanduser()
    if not log_path.exists():
        return []
    events: list[Event] = []
    try:
        with log_path.open("r", encoding="utf-8") as handle:
            for lineno, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    event = Event.from_json_line(stripped)
                except ValueError as exc:
                    raise EventLogError(f"事件日志第 {lineno} 行损坏：{log_path}\n{exc}") from None
                if run_id is None or event.run_id == run_id:
                    events.append(event)
    except OSError as exc:
        raise EventLogError(f"事件日志读取失败：{log_path}（{exc}）") from None
    return events


def _format_validation(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(item) for item in err.get("loc", ())) or "<root>"
        parts.append(f"{loc}: {err.get('msg')}")
    return "; ".join(parts)

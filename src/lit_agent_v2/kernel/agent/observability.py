"""Kernel observability: structured events and a JSONL sink."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

__all__ = ["JsonlEventSink", "KernelEvent", "MemoryEventSink"]


@dataclass(frozen=True)
class KernelEvent:
    event_id: str
    ts: str
    type: str
    task_id: str = ""
    step: int | None = None
    tool: str | None = None
    call_id: str | None = None
    severity: str = "info"
    error_code: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


class EventSink(Protocol):
    def emit(self, event_type: str, **payload: Any) -> None: ...


class MemoryEventSink:
    def __init__(self) -> None:
        self.events: list[KernelEvent] = []

    def emit(self, event_type: str, **payload: Any) -> None:
        self.events.append(_event(event_type, payload))


class JsonlEventSink:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def emit(self, event_type: str, **payload: Any) -> None:
        event = _event(event_type, payload)
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(event), ensure_ascii=False, default=str) + "\n")


def _event(event_type: str, payload: dict[str, Any]) -> KernelEvent:
    severity = "error" if event_type.endswith(("failed", "cancelled")) else "info"
    if event_type in {"kernel.model_retry", "kernel.repair", "kernel.context_compacted"}:
        severity = "warning"
    return KernelEvent(
        event_id=uuid.uuid4().hex,
        ts=datetime.now(UTC).isoformat(),
        type=event_type,
        task_id=str(payload.get("task") or ""),
        step=payload.get("step"),
        tool=payload.get("tool"),
        call_id=payload.get("call_id"),
        severity=severity,
        error_code=payload.get("error_code"),
        payload=dict(payload),
    )

"""Kernel event sink (Phase 3.4 / S2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

__all__ = ["EventSink", "emit"]

EventSink = Callable[[dict[str, Any]], None]


def emit(sink: EventSink | None, event: str, **payload: Any) -> None:
    if sink is not None:
        sink({"event": event, **payload})

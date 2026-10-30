"""Kernel checkpoint (Phase 3.4 / S5)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

__all__ = ["CheckpointStore", "KernelCheckpoint"]


@dataclass
class KernelCheckpoint:
    goal: dict[str, Any]
    step: int
    trace: list[dict[str, Any]] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    stop_reason: str = "failed"
    cost_usd: float = 0.0
    context: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "step": self.step,
            "trace": self.trace,
            "output": self.output,
            "stop_reason": self.stop_reason,
            "cost_usd": self.cost_usd,
            "context": self.context,
        }


class CheckpointStore:
    """Path-backed by default; in-memory when path is None."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path
        self._state: KernelCheckpoint | None = None

    def save(self, state: KernelCheckpoint) -> None:
        self._state = state
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(state.to_dict(), ensure_ascii=False), encoding="utf-8")

    def load(self) -> KernelCheckpoint | None:
        if self._state is not None:
            return self._state
        if self.path is not None and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))
            return KernelCheckpoint(**data)
        return None

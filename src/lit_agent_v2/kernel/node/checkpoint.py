"""Step checkpoint for a Node kernel run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["KernelCheckpoint"]


@dataclass
class KernelCheckpoint:
    node_id: str
    step: int = 0
    history: list[dict[str, Any]] = field(default_factory=list)
    trace: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    usage: dict[str, Any] = field(default_factory=dict)
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "node_id": self.node_id,
            "step": self.step,
            "history": self.history,
            "trace": self.trace,
            "cost_usd": self.cost_usd,
            "usage": self.usage,
            "stop_reason": self.stop_reason,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KernelCheckpoint:
        return cls(
            node_id=str(data.get("node_id") or ""),
            step=int(data.get("step") or 0),
            history=list(data.get("history") or []),
            trace=list(data.get("trace") or []),
            cost_usd=float(data.get("cost_usd") or 0.0),
            usage=dict(data.get("usage") or {}),
            stop_reason=data.get("stop_reason"),
        )

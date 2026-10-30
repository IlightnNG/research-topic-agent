"""Kernel contracts (Phase 3.4 / S1). No workflow planning here."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

__all__ = ["KernelGoal", "KernelResult", "KernelState", "StopReason", "ToolCallRecord"]

StopReason = Literal[
    "final", "max_steps", "budget", "timeout", "cancelled", "no_progress", "failed"
]


@dataclass(frozen=True)
class KernelGoal:
    """A node-local goal. It cannot add/remove outer workflow nodes."""

    node_id: str
    objective: str
    allowed_tools: tuple[str, ...] = ()
    max_steps: int = 4
    max_usd: float = 0.05
    timeout_s: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "node_id": self.node_id,
            "objective": self.objective,
            "allowed_tools": list(self.allowed_tools),
            "max_steps": self.max_steps,
            "max_usd": self.max_usd,
            "timeout_s": self.timeout_s,
        }


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    args: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error_code: str | None = None
    output: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "args": self.args,
            "ok": self.ok,
            "error_code": self.error_code,
            "output": self.output,
        }


@dataclass
class KernelState:
    goal: KernelGoal
    step: int = 0
    trace: list[ToolCallRecord] = field(default_factory=list)
    output: dict[str, Any] = field(default_factory=dict)
    stop_reason: StopReason = "failed"
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal.to_dict(),
            "step": self.step,
            "trace": [item.to_dict() for item in self.trace],
            "output": self.output,
            "stop_reason": self.stop_reason,
            "cost_usd": self.cost_usd,
        }


@dataclass
class KernelResult:
    output: dict[str, Any]
    trace: list[ToolCallRecord]
    steps_used: int
    stop_reason: StopReason
    cost_usd: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "output": self.output,
            "trace": [item.to_dict() for item in self.trace],
            "steps_used": self.steps_used,
            "stop_reason": self.stop_reason,
            "cost_usd": self.cost_usd,
        }

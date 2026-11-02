"""Generic AgentKernel contracts: task, policy, result."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

__all__ = ["KernelPolicy", "KernelResult", "KernelTask"]


@dataclass(frozen=True)
class KernelPolicy:
    max_steps: int = 12
    max_usd: float = 0.50
    max_tokens: int = 12000
    max_tool_calls: int = 64
    max_repair: int = 2
    timeout_s: float = 600.0


@dataclass(frozen=True)
class KernelTask:
    task_id: str
    goal: str
    inputs: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    toolset: str = "general"
    policy: KernelPolicy = field(default_factory=KernelPolicy)
    verifier: Callable[[dict[str, Any]], list[str]] | None = None


@dataclass
class KernelResult:
    output: dict[str, Any]
    history: list[dict[str, Any]]
    plan: dict[str, Any] | None
    steps: int
    usage: dict[str, Any]
    cost_usd: float
    stop_reason: str

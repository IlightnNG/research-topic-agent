"""Agent 协议与结果信封（guide §7）。

契约最小化：每个角色只声明 `name / inputs / outputs`，`run()` 返回 `AgentResult`。
**不共享大 state**——P3 拆角色时，输入输出是唯一耦合点（DSH `subagent` 隔离思路）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from lit_agent.models.results import RunContext

__all__ = ["Agent", "AgentResult"]


@dataclass(frozen=True)
class AgentResult:
    ok: bool
    artifacts: dict[str, Any] = field(default_factory=dict)
    events: list[dict[str, Any]] = field(default_factory=list)
    error_code: str | None = None


@runtime_checkable
class Agent(Protocol):
    name: str
    inputs: tuple[str, ...]
    outputs: tuple[str, ...]

    def run(self, ctx: RunContext) -> AgentResult: ...

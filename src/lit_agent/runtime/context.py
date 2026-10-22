"""RunContext（S3）：一次运行所需的"活"依赖，通过 LangGraph configurable 传入。

为什么不在节点里 `new` 服务：
- gateway 单例（缓存/预算/熔断共享）；
- 预算必须是**活对象**（续跑也不能清零）；
- 节点只依赖 ctx，单测可注入假 gateway。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lit_agent.config import Settings
from lit_agent.runtime.budget import RunBudget

__all__ = ["RunContext"]


@dataclass
class RunContext:
    settings: Settings
    run_id: str
    topic_id: str
    budget: RunBudget
    log: Any | None = None
    gateway: Any | None = None
    transitions_enabled: bool = True
    gates_enabled: bool = True
    attempts: dict[str, int] = field(default_factory=dict)
    tools: Any | None = None
    pdf_enabled: bool = False

    @property
    def engine(self) -> Any:
        """惰性单例引擎（节点不再各建各的）。"""
        from lit_agent.db.session import make_engine

        if getattr(self, "_engine", None) is None:
            self._engine = make_engine(self.settings)
        return self._engine

    def close(self) -> None:
        engine = getattr(self, "_engine", None)
        if engine is not None:
            engine.dispose()
            self._engine = None

    def observation(self, state: dict[str, Any], stage: str) -> dict[str, Any]:
        """给守卫的观测：是"本阶段"的累计量，不是单步增量（避免停滞误报）。"""
        counters = dict(state.get("counters") or {})
        observation: dict[str, Any] = {"stage": stage, "counters": counters}
        # 只有"会产出"的阶段才参与停滞/无进展判定，避免把 parse/normalize 这类
        # 纯统计阶段误判为"没有进展"（Phase 1 的真实误报）。
        if stage in {"retrieval", "analysis", "report"}:
            observation["produced"] = int(counters.get("claims", 0)) + int(
                counters.get("selected", 0)
            )
            observation["artifacts"] = len(state.get("artifacts") or {})
        return observation

"""守卫：`Guard` 协议 + `GuardRail` + Phase 1 的两个最小检测器（guide §7）。

**纯判定，不写事件**（事件由 runner 发）：这样同一条守卫既能被单测直接调用，
也能被 LangGraph 条件边复用。

Phase 1 只实现：
- `BudgetGuardAdapter`：把 `RunBudget` 的三维状态映射成判决；
- `NoProgressGuard`：连续 N 步没有新增产物 → warn（degrade）。
其余四类（drift / loop / advanced-stagnation / timeout）显式 `E_FEATURE_DISABLED`（P2）。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent.errors import E_FEATURE_DISABLED, E_GUARD_STAGNATION, LitError
from lit_agent.models.verdict import GuardAction, GuardSeverity, Verdict
from lit_agent.runtime.budget import RunBudget

__all__ = [
    "BudgetGuardAdapter",
    "Guard",
    "GuardRail",
    "NoProgressGuard",
    "guard_rail",
]

_ACTION_ORDER = {
    GuardAction.CONTINUE: 0,
    GuardAction.ANNOTATE: 1,
    GuardAction.RETRY: 2,
    GuardAction.DEGRADE: 3,
    GuardAction.REPLAN: 4,
    GuardAction.ABORT: 5,
}


class Guard(Protocol):
    name: str

    def check(self, observation: dict[str, Any]) -> Verdict | None: ...


@dataclass
class BudgetGuardAdapter:
    budget: RunBudget
    name: str = "G8_budget"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        state = self.budget.check()
        if state == "ok":
            return None
        snapshot = self.budget.snapshot()
        if state == "warn":
            return Verdict(
                ok=True,
                severity=GuardSeverity.WARN,
                action=GuardAction.DEGRADE,
                code="E_BUDGET_NEAR_LIMIT",
                reasons=[f"预算使用率 {snapshot['ratios']}"],
            )
        return Verdict(
            ok=False,
            severity=GuardSeverity.BLOCK,
            action=GuardAction.ABORT,
            code="E_BUDGET_EXCEEDED",
            reasons=[f"预算已达上限 {snapshot['ratios']}"],
        )


@dataclass
class NoProgressGuard:
    """连续 `no_progress_steps` 步产物数量不变 → 停滞。"""

    no_progress_steps: int = 2
    name: str = "G5_no_progress"
    _history: deque[int] = field(default_factory=lambda: deque(maxlen=6))

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        produced = int(observation.get("produced", 0))
        self._history.append(produced)
        if len(self._history) <= self.no_progress_steps:
            return None
        recent = list(self._history)[-(self.no_progress_steps + 1) :]
        if recent[-1] > recent[0]:
            return None
        return Verdict(
            ok=True,
            severity=GuardSeverity.WARN,
            action=GuardAction.DEGRADE,
            code=E_GUARD_STAGNATION,
            reasons=[f"连续 {self.no_progress_steps} 步无新增（{recent}）"],
        )


def _heaviest(verdicts: list[Verdict]) -> Verdict | None:
    if not verdicts:
        return None
    return max(
        verdicts,
        key=lambda item: (_ACTION_ORDER[item.action], item.severity == GuardSeverity.BLOCK),
    )


@dataclass
class GuardRail:
    """多个守卫合成一个判决：取"最重动作"，reasons 聚合。"""

    guards: list[Guard] = field(default_factory=list)

    def run(self, observation: dict[str, Any]) -> Verdict | None:
        verdicts = [verdict for guard in self.guards if (verdict := guard.check(observation))]
        return _heaviest(verdicts)


def guard_rail(budget: RunBudget, *, no_progress_steps: int = 2) -> GuardRail:
    return GuardRail(
        guards=[
            BudgetGuardAdapter(budget=budget),
            NoProgressGuard(no_progress_steps=no_progress_steps),
        ]
    )


def unimplemented_guard(name: str) -> None:
    """drift / loop / timeout 等四类留给 Phase 2（P2-GUARD-01）。"""
    raise LitError(E_FEATURE_DISABLED, f"守卫 {name} 在 Phase 2 实现", context={"guard": name})

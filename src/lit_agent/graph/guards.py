"""守卫（S8）：全 15 类 + 动作阶梯。

设计
- **纯判定**：只读 observation（由 state 派生的字典），不写库、不发事件；
- **阶梯**：`retry(提醒) → degrade → replan → abort`，由 `GuardRail` 取最重动作；
- **可观测口径**：零值型守卫要求"该阶段确实写过计数"，避免空状态误报（Phase 1 教训 #5）。

编号对应 design/guide 的 G1–G15。
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent.models.verdict import GuardAction, GuardSeverity, Verdict
from lit_agent.runtime.budget import RunBudget

__all__ = [
    "BudgetGuardAdapter",
    "CitationIntegrityGuard",
    "EvalQualityGuard",
    "EvidenceSufficiencyGuard",
    "Guard",
    "GuardRail",
    "GroundingRatioGuard",
    "LoopGuard",
    "NoProgressGuard",
    "ParseFailureGuard",
    "RepeatToolGuard",
    "RetrievalFailureGuard",
    "SchemaOutputGuard",
    "ScopeDriftGuard",
    "StagnationGuard",
    "TimeoutGuard",
    "ZeroNewPapersGuard",
    "guard_rail",
    "unimplemented_guard",
]

_ORDER = {
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


def _n(observation: dict[str, Any], key: str) -> int:
    try:
        return int((observation.get("counters") or {}).get(key, 0))
    except (TypeError, ValueError):
        return 0


def _has(observation: dict[str, Any], key: str) -> bool:
    return key in (observation.get("counters") or {})


def _verdict(
    *,
    code: str,
    action: GuardAction,
    severity: GuardSeverity,
    reason: str,
    ok: bool = True,
) -> Verdict:
    return Verdict(ok=ok, severity=severity, action=action, code=code, reasons=[reason])


# --------------------------------------------------------------------------- #
# G1–G6：数据与阶段
# --------------------------------------------------------------------------- #
@dataclass
class ScopeDriftGuard:
    name: str = "G1_scope_drift"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        if _n(observation, "drift_block"):
            return _verdict(
                code="E_GUARD_DRIFT",
                action=GuardAction.ABORT,
                severity=GuardSeverity.BLOCK,
                reason="漂移阻断：本轮范围与 topic scope 冲突",
                ok=False,
            )
        if _n(observation, "drift_warn"):
            return _verdict(
                code="E_GUARD_DRIFT",
                action=GuardAction.ANNOTATE,
                severity=GuardSeverity.WARN,
                reason="漂移告警：建议补充 scope 提示",
            )
        return None


@dataclass
class RetrievalFailureGuard:
    name: str = "G2_retrieval_failure"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        errors = _n(observation, "retrieval_errors")
        if not errors:
            return None
        return _verdict(
            code="E_SRC_TIMEOUT",
            action=GuardAction.RETRY,
            severity=GuardSeverity.WARN,
            reason=f"检索失败 {errors} 次，退避重试",
        )


@dataclass
class ZeroNewPapersGuard:
    name: str = "G3_zero_new"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        if _has(observation, "new_papers") and _n(observation, "new_papers") == 0:
            return _verdict(
                code="E_SRC_SCHEMA",
                action=GuardAction.DEGRADE,
                severity=GuardSeverity.WARN,
                reason="本轮零新增：降级为现有语料",
            )
        return None


@dataclass
class ParseFailureGuard:
    name: str = "G4_parse_failure"
    threshold: int = 1

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        failed = _n(observation, "parse_failed")
        if failed < self.threshold:
            return None
        return _verdict(
            code="E_SCHEMA_STAGE_OUTPUT",
            action=GuardAction.DEGRADE,
            severity=GuardSeverity.WARN,
            reason=f"{failed} 篇解析失败，跳过这些论文",
        )


@dataclass
class SchemaOutputGuard:
    name: str = "G5_schema_output"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        errors = _n(observation, "schema_errors")
        if not errors:
            return None
        return _verdict(
            code="E_SCHEMA_STAGE_OUTPUT",
            action=GuardAction.RETRY,
            severity=GuardSeverity.WARN,
            reason=f"阶段输出 schema 失败 {errors} 次，重试一次",
        )


@dataclass
class EvidenceSufficiencyGuard:
    name: str = "G6_evidence"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        if _has(observation, "cards") and _n(observation, "cards") == 0:
            return _verdict(
                code="E_GROUND_NO_EVIDENCE",
                action=GuardAction.RETRY,
                severity=GuardSeverity.WARN,
                reason="证据为空：扩大检索范围",
            )
        return None


# --------------------------------------------------------------------------- #
# G7–G11：过程
# --------------------------------------------------------------------------- #
@dataclass
class NoProgressGuard:
    """连续 N 步**累计产出**没有增长 → 停滞（Phase 1 曾误用单步增量，已纠正）。"""

    no_progress_steps: int = 2
    name: str = "G7_no_progress"
    _history: deque[int] = field(default_factory=lambda: deque(maxlen=8))

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        produced = int(observation.get("produced", 0))
        self._history.append(produced)
        if len(self._history) <= self.no_progress_steps:
            return None
        recent = list(self._history)[-(self.no_progress_steps + 1) :]
        if recent[-1] > recent[0]:
            return None
        return _verdict(
            code="E_GUARD_STAGNATION",
            action=GuardAction.DEGRADE,
            severity=GuardSeverity.WARN,
            reason=f"连续 {self.no_progress_steps} 步无新增（{recent}）",
        )


@dataclass
class RepeatToolGuard:
    """重复工具调用：先**提醒**（retry，不打断），多次后升级 replan。"""

    remind_after: int = 1
    escalate_after: int = 3
    name: str = "G8_repeat_tool"
    _seen: deque[str] = field(default_factory=lambda: deque(maxlen=16))

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        tool = str(observation.get("tool") or "")
        if not tool:
            return None
        repeats = sum(1 for item in self._seen if item == tool)
        self._seen.append(tool)
        if repeats >= self.escalate_after:
            return _verdict(
                code="E_GUARD_LOOP",
                action=GuardAction.REPLAN,
                severity=GuardSeverity.WARN,
                reason=f"工具 {tool} 已重复 {repeats + 1} 次，强制换策略",
            )
        if repeats >= self.remind_after:
            return _verdict(
                code="E_GUARD_LOOP",
                action=GuardAction.RETRY,
                severity=GuardSeverity.INFO,
                reason=f"提醒：工具 {tool} 重复调用，请换方法或收尾",
            )
        return None


@dataclass
class CitationIntegrityGuard:
    name: str = "G9_citation_integrity"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        unresolved = _n(observation, "unresolved_citations")
        if not unresolved:
            return None
        return _verdict(
            code="E_GROUND_UNRESOLVED_CITATION",
            action=GuardAction.RETRY,
            severity=GuardSeverity.BLOCK,
            reason=f"{unresolved} 条 claim 引用不可解析，需重写",
            ok=False,
        )


@dataclass
class GroundingRatioGuard:
    name: str = "G10_grounding_ratio"
    min_ratio: float = 0.6

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        ratio = observation.get("grounding_rate")
        if ratio is None:
            return None
        if float(ratio) >= self.min_ratio:
            return None
        return _verdict(
            code="E_GROUND_UNSUPPORTED_RATIO",
            action=GuardAction.DEGRADE,
            severity=GuardSeverity.WARN,
            reason=f"grounding {float(ratio):.2f} < {self.min_ratio}，降级收尾",
        )


@dataclass
class LoopGuard:
    name: str = "G11_loop"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        loops = _n(observation, "loop")
        if not loops:
            return None
        return _verdict(
            code="E_GUARD_LOOP",
            action=GuardAction.REPLAN,
            severity=GuardSeverity.WARN,
            reason=f"检测到循环 {loops} 次，强制 replan",
        )


# --------------------------------------------------------------------------- #
# G12–G15：资源与评测
# --------------------------------------------------------------------------- #
@dataclass
class BudgetGuardAdapter:
    budget: RunBudget
    name: str = "G12_budget"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        state = self.budget.check()
        if state == "ok":
            return None
        snapshot = self.budget.snapshot()
        if state == "warn":
            return _verdict(
                code="E_BUDGET_NEAR_LIMIT",
                action=GuardAction.DEGRADE,
                severity=GuardSeverity.WARN,
                reason=f"预算使用率 {snapshot['ratios']}",
            )
        return _verdict(
            code="E_BUDGET_EXCEEDED",
            action=GuardAction.ABORT,
            severity=GuardSeverity.BLOCK,
            reason=f"预算已达上限 {snapshot['ratios']}",
            ok=False,
        )


@dataclass
class TimeoutGuard:
    name: str = "G13_timeout"
    stale_seconds: float = 600.0

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        idle = observation.get("idle_seconds")
        if idle is None:
            return None
        if float(idle) < self.stale_seconds:
            return None
        return _verdict(
            code="E_GUARD_TIMEOUT",
            action=GuardAction.ABORT,
            severity=GuardSeverity.BLOCK,
            reason=f"空闲 {idle}s 超过阈值 {self.stale_seconds}s",
            ok=False,
        )


@dataclass
class StagnationGuard:
    name: str = "G14_stagnation"
    no_progress_steps: int = 3
    _history: deque[int] = field(default_factory=lambda: deque(maxlen=8))

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        artifacts = int(observation.get("artifacts", 0))
        self._history.append(artifacts)
        if len(self._history) <= self.no_progress_steps:
            return None
        recent = list(self._history)[-(self.no_progress_steps + 1) :]
        if len(set(recent)) > 1:
            return None
        return _verdict(
            code="E_GUARD_STAGNATION",
            action=GuardAction.REPLAN,
            severity=GuardSeverity.WARN,
            reason=f"连续 {self.no_progress_steps} 步产物数不变（{artifacts}），触发 replan",
        )


@dataclass
class EvalQualityGuard:
    name: str = "G15_eval_quality"

    def check(self, observation: dict[str, Any]) -> Verdict | None:
        if _n(observation, "retries_exhausted"):
            return _verdict(
                code="E_GUARD_STAGNATION",
                action=GuardAction.DEGRADE,
                severity=GuardSeverity.WARN,
                reason="重试已用尽，标注低置信收尾",
            )
        if _n(observation, "eval_below"):
            return _verdict(
                code="E_GUARD_UNCALIBRATED",
                action=GuardAction.ANNOTATE,
                severity=GuardSeverity.WARN,
                reason="评测不达标，输出告警标注",
            )
        return None


# --------------------------------------------------------------------------- #
# 组合
# --------------------------------------------------------------------------- #
def _heaviest(verdicts: list[Verdict]) -> Verdict | None:
    if not verdicts:
        return None
    return max(
        verdicts,
        key=lambda item: (_ORDER[item.action], item.severity == GuardSeverity.BLOCK),
    )


@dataclass
class GuardRail:
    guards: list[Guard] = field(default_factory=list)

    def run(self, observation: dict[str, Any]) -> Verdict | None:
        verdicts = [verdict for guard in self.guards if (verdict := guard.check(observation))]
        return _heaviest(verdicts)

    @property
    def names(self) -> list[str]:
        return [guard.name for guard in self.guards]


def guard_rail(budget: RunBudget, *, no_progress_steps: int = 2) -> GuardRail:
    """默认装配 15 类守卫。"""
    return GuardRail(
        guards=[
            ScopeDriftGuard(),
            RetrievalFailureGuard(),
            ZeroNewPapersGuard(),
            ParseFailureGuard(),
            SchemaOutputGuard(),
            EvidenceSufficiencyGuard(),
            NoProgressGuard(no_progress_steps=no_progress_steps),
            RepeatToolGuard(),
            CitationIntegrityGuard(),
            GroundingRatioGuard(),
            LoopGuard(),
            BudgetGuardAdapter(budget=budget),
            TimeoutGuard(),
            StagnationGuard(),
            EvalQualityGuard(),
        ]
    )


def unimplemented_guard(name: str) -> None:
    """保留给 P3 的学习型守卫。"""
    from lit_agent.errors import E_FEATURE_DISABLED, LitError

    raise LitError(E_FEATURE_DISABLED, f"守卫 {name} 在 P3 实现", context={"guard": name})

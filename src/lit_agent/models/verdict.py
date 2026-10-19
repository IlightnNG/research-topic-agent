"""守卫判决契约（**以 `design/state-machine-and-guards.md` 为准**）。

- `GuardVerdict{ok, severity, action, code, reasons[]}`；
- `severity`：`info`（仅记录）→ `warn`（可修复，继续尝试）→ `block`（必须改变策略或终止）；
- `action`：`continue / retry / degrade / replan / abort / annotate`；
- 升级阶梯：`retry(≤2) → degrade(≤2) → replan(≤1) → abort(annotate)`。
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from lit_agent.models._base import ContractModel

__all__ = ["GuardAction", "GuardSeverity", "GuardVerdict", "Verdict"]


class GuardSeverity(StrEnum):
    """判决严重度（与日志 `Severity` 是两套词表，勿混用）。"""

    INFO = "info"
    WARN = "warn"
    BLOCK = "block"


class GuardAction(StrEnum):
    """守卫判决动作（升级阶梯，见 state-machine-and-guards §8）。"""

    CONTINUE = "continue"
    RETRY = "retry"
    DEGRADE = "degrade"
    REPLAN = "replan"
    ABORT = "abort"
    ANNOTATE = "annotate"


class GuardVerdict(ContractModel):
    ok: bool
    severity: GuardSeverity = GuardSeverity.INFO
    action: GuardAction = GuardAction.CONTINUE
    code: str = Field(min_length=1, description="错误/判决码，如 E_GUARD_DRIFT")
    reasons: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _require_reasons_on_failure(self) -> GuardVerdict:
        if not self.ok and not self.reasons:
            raise ValueError("ok=False 的判决必须给出至少 1 条 reasons")
        return self


#: 兼容别名：Phase 0 的 `Verdict` 名字沿用，语义完全等价（设计文档用 `GuardVerdict`）。
Verdict = GuardVerdict

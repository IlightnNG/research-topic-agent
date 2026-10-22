"""supervisor（S3）：把门禁 + 守卫合成一条可执行决策。

- 纯函数：不做 IO、不发事件；
- 取"最重动作"（abort > replan > degrade > repair > retry > annotate > continue）；
- 回边目标由 `graph/transitions.py` 的映射决定，supervisor 只给动作与理由。
"""

from __future__ import annotations

from lit_agent.contracts.nodeio import Decision, GateResult
from lit_agent.models.verdict import GuardAction, Verdict
from lit_agent.runtime.context import RunContext

__all__ = ["ACTION_ORDER", "decide"]

ACTION_ORDER: dict[str, int] = {
    "continue": 0,
    "annotate": 1,
    "retry": 2,
    "repair": 2,
    "degrade": 3,
    "replan": 4,
    "abort": 5,
}

#: 动作 → 回边目标（S4 使用；S3 仅 abort/degrade 真正执行）
TARGETS: dict[str, str] = {"repair": "analysis", "retry": "", "replan": "retrieval"}

_GUARD_ACTION: dict[GuardAction, str] = {
    GuardAction.CONTINUE: "continue",
    GuardAction.ANNOTATE: "annotate",
    GuardAction.RETRY: "retry",
    GuardAction.DEGRADE: "degrade",
    GuardAction.REPLAN: "replan",
    GuardAction.ABORT: "abort",
}


def decide(
    *,
    stage: str,
    gates: list[GateResult],
    guard: Verdict | None,
    ctx: RunContext,
    attempt: int,
) -> Decision:
    """返回一条决策；无异常时 action=continue。"""
    candidates: list[tuple[str, str, list[str], str]] = []

    for gate in gates:
        candidates.append((gate.action, gate.code, list(gate.reasons), "gate"))

    if guard is not None and guard.action is not GuardAction.CONTINUE:
        candidates.append(
            (_GUARD_ACTION[guard.action], guard.code, list(guard.reasons), "guard")
        )

    # 预算硬顶优先：无论门禁怎么说都必须停
    if ctx.budget.check() == "stop":
        candidates.append(("abort", "E_BUDGET_EXCEEDED", ["预算已达上限"], "gate"))

    if not candidates:
        return Decision(action="continue", source="none", attempt=attempt)

    action, code, reasons, source = max(
        candidates, key=lambda item: (ACTION_ORDER[item[0]], item[1] == "abort")
    )

    target: str | None = None
    if action == "repair":
        repair_targets = [
            gate.details.get("repair_target")
            for gate in gates
            if gate.action == "repair"
        ]
        target = next((item for item in repair_targets if item), "analysis")
    elif action == "retry":
        target = stage
    elif action == "replan":
        target = "retrieval"

    drop: list[int] = []
    if action in {"repair", "degrade"}:
        for gate in gates:
            if gate.name == "citation_integrity":
                drop.extend(int(index) for index in gate.details.get("bad_indexes") or [])

    return Decision(
        action=action,  # type: ignore[arg-type]
        target=target,
        code=code,
        reasons=reasons,
        source=source,  # type: ignore[arg-type]
        attempt=attempt,
        drop_claim_indexes=drop,
    )

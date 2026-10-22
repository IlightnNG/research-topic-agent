"""有界回边（S4）：动作 → 目标节点 + 次数上限。

只做**纯函数**：读 `state.attempts` / `state.decisions`，返回下一跳。
上限口径：`attempts[target] < MAX_ATTEMPTS[target]` 才允许回边；
否则由 runner 降级（不允许无限重试）。
"""

from __future__ import annotations

from typing import Any

from lit_agent.graph.edges import MAINLINE

__all__ = ["MAX_ATTEMPTS", "is_back_action", "next_stage"]

#: 各节点允许的尝试次数（1 = 不允许重跑）
MAX_ATTEMPTS: dict[str, int] = {
    "analysis": 2,
    "critique": 2,
    "retrieval": 2,
    "report": 1,
}

BACK_ACTIONS = {"retry", "repair", "replan"}


def is_back_action(action: str | None) -> bool:
    return action in BACK_ACTIONS


def _last(state: dict[str, Any]) -> dict[str, Any] | None:
    decisions = state.get("decisions") or []
    return decisions[-1] if decisions else None


def next_stage(stage: str, state: dict[str, Any]) -> str:
    """返回下一节点名或 `"end"`。"""
    decision = _last(state)
    if decision and is_back_action(decision.get("action")):
        target = str(decision.get("target") or "")
        attempts = int((state.get("attempts") or {}).get(target, 0))
        limit = MAX_ATTEMPTS.get(target, 1)
        if target and attempts < limit:
            return target
    if stage in MAINLINE:
        index = MAINLINE.index(stage)
        return MAINLINE[index + 1] if index + 1 < len(MAINLINE) else "end"
    return "end"

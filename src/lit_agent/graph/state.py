"""`AgentState` 契约（guide §6，**冻结**）。

约束
- 必须可 JSON 序列化（checkpoint 需要）；不可序列化资源放 `RunContext.resources`；
- 大正文不进 state（只放引用/摘要），避免 checkpoint 膨胀；
- `events`/`errors` 用 `operator.add` 归约，节点只返回增量。
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, TypedDict

__all__ = ["STATE_SCHEMA_VERSION", "AgentState", "new_state"]

STATE_SCHEMA_VERSION = "1.1"


def _merge_dicts(left: dict, right: dict) -> dict:
    """节点返回的增量字典必须**合并**而不是覆盖（artifacts/counters 都依赖它）。"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


class AgentState(TypedDict, total=False):
    """跨节点传递的最小状态。`total=False` 允许节点只返回增量字段。"""

    run_id: str
    topic_id: str
    stage: str
    attempt: int
    input_hash: str
    retry_budget: int
    errors: Annotated[list[str], operator.add]
    events: Annotated[list[dict[str, Any]], operator.add]
    artifacts: Annotated[dict[str, Any], _merge_dicts]
    counters: Annotated[dict[str, int], _merge_dicts]
    verdict: dict[str, Any] | None
    focus_hint: str | None
    edge: str | None
    budget: dict[str, Any]


def new_state(
    *, run_id: str, topic_id: str, input_hash: str = "", retry_budget: int = 2
) -> AgentState:
    return {
        "run_id": run_id,
        "topic_id": topic_id,
        "stage": "intake",
        "attempt": 1,
        "input_hash": input_hash,
        "retry_budget": retry_budget,
        "errors": [],
        "events": [],
        "artifacts": {},
        "counters": {},
        "verdict": None,
    }

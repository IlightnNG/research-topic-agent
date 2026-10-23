"""LangGraph 构建器（Phase 2：十节点主干 + 条件边）。

- `build_phase2_graph(settings, checkpointer)`：S0–S9 十节点，条件边由 `edges.route_after` 决定；
- `build_graph(nodes, checkpointer)`：Phase 1 的线性冒烟图（保留给旧测试）；
- 节点签名统一 `(state) -> dict`（只返回增量）。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from lit_agent.config import Settings
from lit_agent.errors import E_SCHEMA_STAGE_OUTPUT, LitError
from lit_agent.graph.checkpoint import thread_config
from lit_agent.graph.edges import route_after
from lit_agent.graph.nodes import PHASE2_STAGES, Phase2Nodes
from lit_agent.graph.state import AgentState, new_state

__all__ = [
    "PHASE2_STAGES",
    "SMOKE_MAINLINE",
    "build_graph",
    "build_phase2_graph",
    "invoke_once",
    "make_node",
    "register_node",
    "smoke_graph",
]

NodeFn = Callable[[AgentState], dict[str, Any]]

#: Phase 1 的三节点冒烟链（保持旧测试语义，与十节点主干无关）
SMOKE_MAINLINE: tuple[str, ...] = ("intake", "retrieve", "draft")


def make_node(name: str) -> NodeFn:
    """冒烟用的最小阶段：记录阶段事件 + 计数。"""

    def node(state: AgentState) -> dict[str, Any]:
        counters = dict(state.get("counters") or {})
        counters[name] = counters.get(name, 0) + 1
        return {
            "stage": name,
            "events": [{"stage": name, "type": "phase_change", "run_id": state.get("run_id")}],
            "counters": counters,
        }

    return node


def build_graph(
    nodes: dict[str, NodeFn] | None = None,
    *,
    checkpointer: Any | None = None,
    mainline: tuple[str, ...] = SMOKE_MAINLINE,
) -> Any:
    """线性主干图（Phase 1 冒烟用；mainline 可自定义）。"""
    from langgraph.graph import END, START, StateGraph

    if not mainline:
        raise LitError(E_SCHEMA_STAGE_OUTPUT, "mainline 不能为空")
    builder: Any = StateGraph(AgentState)
    for name in mainline:
        builder.add_node(name, (nodes or {}).get(name) or make_node(name))
    builder.add_edge(START, mainline[0])
    for left, right in zip(mainline, mainline[1:], strict=False):
        builder.add_edge(left, right)
    builder.add_edge(mainline[-1], END)
    return builder.compile(checkpointer=checkpointer)


def build_phase2_graph(
    settings: Settings,
    *,
    nodes: dict[str, NodeFn] | None = None,
    checkpointer: Any | None = None,
) -> Any:
    """十节点主干 + 条件边（S2/S3）。

    条件边策略：每个节点之后调用 `route_after(stage, state)`：
    - 命中回退动作（abort/replan/retry/...）→ 记录到 state 并由 runner 解释；
    - 否则进入下一阶段；最后一节点 → END。
    为了保持图可编译且可续跑，回退动作不在此处"跳转节点"，而是写入 `state.edge`，
    由 runner 在节点边界统一处理（避免图出现未定义节点）。
    """
    from langgraph.graph import END, START, StateGraph

    impl = Phase2Nodes(settings)
    builder: Any = StateGraph(AgentState)

    actions = {"abort", "replan", "retry", "degrade", "skip", "annotate", "expand", "rewrite", "warn"}

    def wrap(name: str) -> NodeFn:
        base: NodeFn = (nodes or {}).get(name) or getattr(impl, name)

        def node(state: AgentState) -> dict[str, Any]:
            patch = base(state)
            merged = dict(state)
            merged["counters"] = {**(state.get("counters") or {}), **(patch.get("counters") or {})}
            merged["artifacts"] = {**(state.get("artifacts") or {}), **(patch.get("artifacts") or {})}
            next_hop = route_after(name, merged)
            patch.setdefault("counters", {})
            patch["stage"] = name
            patch["edge"] = next_hop if next_hop in actions else None
            patch["edges"] = [next_hop] if next_hop in actions else []
            return patch

        return node

    from lit_agent.graph.transitions import next_stage

    limits = dict(settings.pipeline.limits.max_attempts)

    def route(state: Any, stage: str) -> Any:
        target = next_stage(stage, state, limits)
        return END if target == "end" else target

    for name in PHASE2_STAGES:
        builder.add_node(name, wrap(name))
    builder.add_edge(START, PHASE2_STAGES[0])
    for name in PHASE2_STAGES:
        builder.add_conditional_edges(name, lambda state, _stage=name: route(state, _stage))
    return builder.compile(checkpointer=checkpointer)


def register_node(builder: Any, name: str, fn: NodeFn) -> None:
    builder.add_node(name, fn)


def smoke_graph(*, checkpointer: Any | None = None) -> Any:
    return build_graph(checkpointer=checkpointer)


def invoke_once(
    graph: Any,
    *,
    run_id: str | None = None,
    topic_id: str = "ai-agents",
    with_thread: bool = True,
) -> tuple[dict[str, Any], str]:
    """跑一次完整链路，返回 (最终状态, run_id)。"""
    rid = run_id or f"run-{uuid.uuid4().hex[:8]}"
    state = new_state(run_id=rid, topic_id=topic_id)
    config = thread_config(rid) if with_thread else None
    return graph.invoke(state, config), rid

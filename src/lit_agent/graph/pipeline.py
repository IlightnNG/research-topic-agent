"""LangGraph 构建器 + 三节点冒烟链（Step 1.10，D-MIN）。

- `build_graph(nodes, checkpointer)`：把"阶段函数"接成线性主干（Phase 2 再铺 S0–S9 全边）；
- `smoke_graph()`：intake → retrieve → draft，用来验证接线/归约/checkpoint 三件事；
- 节点签名统一 `(state) -> dict`（只返回增量），与 `RunContext` 版阶段函数在 1.11 对齐。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from lit_agent.errors import E_SCHEMA_STAGE_OUTPUT, LitError
from lit_agent.graph.checkpoint import thread_config
from lit_agent.graph.edges import MAINLINE
from lit_agent.graph.state import AgentState, new_state

__all__ = ["build_graph", "invoke_once", "make_node", "register_node", "smoke_graph"]

NodeFn = Callable[[AgentState], dict[str, Any]]


def make_node(name: str) -> NodeFn:
    """冒烟用的最小阶段：记录阶段事件 + 计数（真实逻辑在 Step 1.11 接入）。"""

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
    mainline: tuple[str, ...] = MAINLINE,
) -> Any:
    """构建线性主干图；未提供的节点用 `make_node(name)` 兜底。"""
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


def register_node(builder: Any, name: str, fn: NodeFn) -> None:
    """Phase 2 用：向已有 builder 追加节点（Phase 1 仅供测试/扩展）。"""
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

"""Step 1.10 Harness 骨架：state 契约、主干路由、三节点冒烟、checkpoint 续跑。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.errors import E_FEATURE_DISABLED, LitError
from lit_agent.graph.checkpoint import open_checkpointer, resume, thread_config
from lit_agent.graph.edges import EDGES, MAINLINE, backoff_edge, route_after
from lit_agent.graph.pipeline import build_graph, invoke_once, make_node, smoke_graph
from lit_agent.graph.state import STATE_SCHEMA_VERSION, new_state


def test_new_state_contract() -> None:
    state = new_state(run_id="r1", topic_id="t1", input_hash="h")
    assert state["stage"] == "intake"
    assert state["errors"] == [] and state["events"] == []
    assert state["retry_budget"] == 2
    assert STATE_SCHEMA_VERSION == "1.0"


def test_smoke_graph_runs_three_nodes_in_order() -> None:
    graph = smoke_graph()
    final, run_id = invoke_once(graph, run_id="r-smoke")

    assert [event["stage"] for event in final["events"]] == ["intake", "retrieve", "draft"]
    assert final["stage"] == "draft"
    assert final["counters"] == {"intake": 1, "retrieve": 1, "draft": 1}
    assert run_id == "r-smoke"


def test_edges_registry_covers_e1_to_e13() -> None:
    assert set(EDGES) == {f"E{index}" for index in range(1, 14)}
    assert MAINLINE == ("intake", "retrieve", "draft")


def test_mainline_router() -> None:
    assert route_after("intake", {}) == "retrieve"
    assert route_after("retrieve", {}) == "draft"
    assert route_after("draft", {}) == "end"


def test_backoff_edges_are_explicitly_unimplemented() -> None:
    with pytest.raises(LitError) as excinfo:
        route_after("scope", {})
    assert excinfo.value.code == E_FEATURE_DISABLED

    with pytest.raises(LitError):
        backoff_edge("E11")
    with pytest.raises(ValueError):
        backoff_edge("E99")


def test_reducers_append_events_across_nodes() -> None:
    custom = {"retrieve": lambda state: {"events": [{"stage": "retrieve-extra"}]}}
    graph = build_graph(custom)
    final, _ = invoke_once(graph, run_id="r-append", with_thread=False)

    stages = [event["stage"] for event in final["events"]]
    # 自定义节点替换了默认 retrieve 节点 → 事件序列为 intake / retrieve-extra / draft
    assert stages == ["intake", "retrieve-extra", "draft"]
    assert len(final["events"]) == 3


def test_checkpoint_persists_and_resume_uses_none(tmp_path: Path) -> None:
    saver, connection = open_checkpointer(tmp_path / "ckpt.db")
    try:
        graph = build_graph(checkpointer=saver)
        first, run_id = invoke_once(graph, run_id="r-ckpt")
        assert first["stage"] == "draft"

        # 续跑只允许 invoke(None)：已完成线程返回同一最终状态，不重放节点
        again = resume(graph, run_id)
        assert again["stage"] == "draft"
        assert [event["stage"] for event in again["events"]] == ["intake", "retrieve", "draft"]

        snapshot = graph.get_state(thread_config(run_id))
        assert snapshot.values["run_id"] == run_id
    finally:
        connection.close()


def test_node_factory_is_pure_increment() -> None:
    node = make_node("retrieve")
    increment = node({"run_id": "r", "counters": {"intake": 1}})
    assert increment["stage"] == "retrieve"
    assert increment["counters"] == {"intake": 1, "retrieve": 1}
    assert "run_id" not in increment or increment.get("run_id") is None

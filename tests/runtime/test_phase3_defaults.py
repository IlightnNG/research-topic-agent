"""3.0 / S4 验收：micro 默认关，关闭时行为与 2.2 一致。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.graph.nodes import PHASE2_STAGES
from lit_agent.runtime.graph_runner import run_graph


def test_micro_disabled_by_default(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    assert settings.pipeline.micro_enabled is False


def test_default_run_still_ten_stages(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_graph(settings, "ai-agents", run_id="p3-off-1")

    events = fetch_events(settings, "p3-off-1")
    starts = [
        event["stage"]
        for event in events
        if event["type"] == "phase_change" and event["payload"].get("phase") == "start"
    ]
    assert [stage for stage in starts if stage in PHASE2_STAGES] == list(PHASE2_STAGES)
    # micro 关闭时不应出现工具调用事件（pdf 也默认关）
    assert not [event for event in events if event["type"] == "tool_call"]


def test_default_run_succeeds_with_claims(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_graph(settings, "ai-agents", run_id="p3-off-2")
    events = fetch_events(settings, "p3-off-2")
    ends = [event for event in events if event["type"] == "phase_change" and event["payload"].get("phase") == "end"]
    assert len(ends) == 10
    assert all(event["payload"].get("ok") for event in ends)

"""3.1 / S7–S10 验收：retrieval L2 可开、可回退、默认不变。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.config import Settings
from lit_agent.runtime.graph_runner import run_graph


def enable_l2(settings: Settings) -> Settings:
    pipeline = settings.pipeline.model_copy(update={"retrieval_l2": True})
    return settings.model_copy(update={"pipeline": pipeline})


def test_default_is_l1(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=3)
    assert settings.pipeline.retrieval_l2 is False
    out = run_graph(settings, "ai-agents", run_id="r-l1", focus_hint="tool use")

    assert out["state"] == "succeeded"
    assert out["stages"]["strategy"] == "hybrid"
    events = fetch_events(settings, "r-l1")
    assert not [event for event in events if event["type"] == "tool_call"]


def test_l2_emits_two_tool_calls(tmp_path: Path) -> None:
    settings = enable_l2(prepare(tmp_path, papers=3))
    run_graph(settings, "ai-agents", run_id="r-l2", focus_hint="tool use")

    events = fetch_events(settings, "r-l2")
    calls = [event for event in events if event["type"] == "tool_call"]
    names = [event["payload"].get("tool") for event in calls]
    assert names == ["rewrite_query", "hybrid_search"], names
    assert all(event["payload"].get("ok") for event in calls)


def test_l2_selection_matches_l1_cards(tmp_path: Path) -> None:
    base = prepare(tmp_path / "l1", papers=3)
    l1 = run_graph(base, "ai-agents", run_id="r-l1b", focus_hint="tool use")

    settings = enable_l2(prepare(tmp_path / "l2", papers=3))
    l2 = run_graph(settings, "ai-agents", run_id="r-l2b", focus_hint="tool use")

    assert l2["stages"]["strategy"] == "l2"
    assert l2["stages"]["l2_steps"] == 2
    assert l2["stages"]["paper_ids"] == l1["stages"]["paper_ids"]
    assert not [event for event in fetch_events(settings, "r-l2b") if event["type"] == "error"]


def test_l2_skipped_without_focus_hint(tmp_path: Path) -> None:
    settings = enable_l2(prepare(tmp_path, papers=3))
    out = run_graph(settings, "ai-agents", run_id="r-l2c")

    assert out["stages"]["strategy"] == "keyword"
    assert not [event for event in fetch_events(settings, "r-l2c") if event["type"] == "tool_call"]


def test_l2_falls_back_to_keyword(tmp_path: Path) -> None:
    settings = enable_l2(prepare(tmp_path, papers=2))
    out = run_graph(settings, "ai-agents", run_id="r-l2d", focus_hint="zzz-nonexistent")

    assert out["stages"]["strategy"] == "l2_fallback"
    assert not [event for event in fetch_events(settings, "r-l2d") if event["type"] == "error"]

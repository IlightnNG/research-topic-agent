"""3.5 / S22 + S26：轨迹指标与日志回放。"""

from __future__ import annotations

from pathlib import Path

from scripts.replay_run import replay

from lit_agent.config import Settings
from lit_agent.eval.metrics import compute_run_metrics
from lit_agent.eval.trajectory import trajectory_metrics
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import prepare


def enable(settings: Settings, **updates: bool) -> Settings:
    return settings.model_copy(update={"pipeline": settings.pipeline.model_copy(update=updates)})


def test_default_trajectory_is_clean(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    run_graph(settings, "ai-agents", run_id="t-clean", focus_hint="tool use")

    metrics = compute_run_metrics(settings, "t-clean")
    assert metrics["steps_total"] == 10
    assert metrics["tool_calls"] == 0
    assert metrics["retries_total"] == 0
    assert metrics["stop_reason"] in {"clean", "degraded"}


def test_l2_trajectory_has_tool_calls(tmp_path: Path) -> None:
    settings = enable(prepare(tmp_path, papers=2), retrieval_l2=True)
    run_graph(settings, "ai-agents", run_id="t-l2", focus_hint="tool use")

    metrics = trajectory_metrics(settings, "t-l2")
    assert metrics["tool_calls"] == 2
    assert metrics["attempts_by_stage"]["retrieval"] == 1


def test_replay_answers_three_questions(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    run_graph(settings, "ai-agents", run_id="t-replay", focus_hint="tool use")

    payload = replay(settings, "t-replay")
    assert payload["run_id"] == "t-replay"
    assert payload["retries"] == []
    assert payload["cost_usd"] == 0.0
    assert payload["duration_ms_total"] > 0
    assert payload["trajectory"]["steps_total"] == 10

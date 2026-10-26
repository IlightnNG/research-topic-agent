"""S5 验收：阶段耗时写入事件、汇总进指标、API 可读。"""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from lit_agent.api.app import create_app
from lit_agent.db.session import connect, make_engine
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import fetch_events, prepare


def test_stage_end_events_carry_duration(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_graph(settings, "ai-agents", run_id="obs-1")

    events = fetch_events(settings, "obs-1")
    ends = [
        event
        for event in events
        if event["type"] == "phase_change" and event["payload"].get("phase") == "end"
    ]
    assert len(ends) == 10, len(ends)
    assert all("duration_ms" in event["payload"] for event in ends)
    assert all(float(event["payload"]["duration_ms"]) >= 0 for event in ends)


def test_metrics_expose_duration_by_stage(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_graph(settings, "ai-agents", run_id="obs-2")

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT metric, value FROM metrics"
                    " WHERE scope = 'run' AND scope_id = 'obs-2'"
                )
            ).all()
    finally:
        engine.dispose()

    stored = {str(metric): float(value) for metric, value in rows}
    stage_keys = [key for key in stored if key.startswith("duration_ms_")]
    assert len(stage_keys) >= 10, sorted(stored)
    assert stored["duration_ms_total"] > 0

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/runs/obs-2/metrics")

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["source"] == "persisted"
    durations = payload["duration_by_stage"]
    assert len(durations) == 10, durations
    assert set(durations) == {
        "intake",
        "scope",
        "retrieval",
        "parse",
        "normalize",
        "mapping",
        "analysis",
        "critique",
        "report",
        "evaluate",
    }
    assert payload["slowest_stage"] in durations
    assert abs(sum(durations.values()) - payload["duration_ms_total"]) < 0.01


def test_unknown_run_metrics_is_404(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/runs/nope/metrics")
    assert response.status_code == 404

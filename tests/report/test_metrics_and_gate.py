"""3.2 / S7：报告指标与 paper API。"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lit_agent.api.app import create_app
from lit_agent.eval.metrics import compute_run_metrics
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import prepare


def test_report_metrics_are_numeric(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    report_settings = settings.report.model_copy(update={"v2_enabled": True})
    settings = settings.model_copy(update={"report": report_settings})
    run_graph(settings, "ai-agents", run_id="metrics-v2", focus_hint="tool use")

    metrics = compute_run_metrics(settings, "metrics-v2")
    assert metrics["report_sections"] is not None
    assert metrics["report_sections"] >= 1
    assert metrics["report_words"] > 0
    assert metrics["report_claims"] >= 1
    assert metrics["report_cited_ratio"] == pytest.approx(1.0)
    assert metrics["report_fallback_count"] is not None
    assert metrics["report_coverage"] is not None
    assert metrics["report_thin"] is not None
    assert metrics["report_cache_hit_rate"] is None or 0.0 <= metrics["report_cache_hit_rate"] <= 1.0


def test_paper_endpoint(tmp_path: Path) -> None:
    client = TestClient(create_app(prepare(tmp_path, papers=1)))
    payload = client.get("/api/papers/P0").json()

    assert payload["paper_id"] == "P0"
    assert "title" in payload
    assert payload["pdf_available"] is False

    missing = client.get("/api/papers/nope")
    assert missing.status_code == 404
    assert missing.json()["code"] == "E_NOT_FOUND"


def test_report_language_zh_per_run(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    client = TestClient(create_app(settings))
    created = client.post(
        "/api/topics/ai-agents/run",
        json={"run_id": "zh-run", "report_language": "zh", "wait": True},
    )
    assert created.status_code == 200
    report = client.get("/api/runs/zh-run/report").json()
    assert report["language"] == "zh"
    assert report["sections"][0]["title"] == "概览"
    assert any("共同点" in section["body"] for section in report["sections"])


def test_thin_report_and_old_metadata_defaults(tmp_path: Path) -> None:
    from sqlalchemy import text

    from lit_agent.db.session import connect, make_engine

    settings = prepare(tmp_path, papers=2)
    client = TestClient(create_app(settings))
    client.post("/api/topics/ai-agents/run", json={"run_id": "thin-run", "wait": True})

    report = client.get("/api/runs/thin-run/report").json()
    assert report["thin"] is True

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text(
                    "UPDATE reports SET language=NULL, generated_by=NULL, fallback_count=NULL,"
                    " coverage=NULL, thin=NULL, word_count=NULL WHERE run_id='thin-run'"
                )
            )
    finally:
        engine.dispose()

    old = client.get("/api/runs/thin-run/report").json()
    assert old["language"] == "en"
    assert old["generated_by"] == "template"
    assert old["fallback_count"] == 0
    assert old["coverage"] == 0.0
    assert old["thin"] is False
    assert old["word_count"] > 0

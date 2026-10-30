"""3.4 / S16-S19: metric store, evaluators and promotion policy."""

from __future__ import annotations

from pathlib import Path

from tests.wiring import prepare

from lit_agent.eval.evaluators import RuleEvaluator
from lit_agent.eval.metric_catalog import CATALOG
from lit_agent.eval.metric_store import (
    collect_report_points,
    load_points,
    record_point,
    record_span,
    seed_definitions,
)
from lit_agent.eval.optimizer import Experiment, decide_promotion, save_experiment
from lit_agent.eval.report_eval import compare_summaries, score_summary, summarize_points
from lit_agent.runtime.graph_runner import run_graph


def test_catalog_has_required_dimensions() -> None:
    for key, item in CATALOG.items():
        assert item.metric_id == key
        assert item.unit
        assert item.formula
        assert item.direction in {"higher_better", "lower_better", "in_range"}


def test_metric_points_and_null_semantics(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    seed_definitions(settings)
    record_point(
        settings,
        "report.words",
        800,
        scope="run",
        scope_id="r1",
        run_id="r1",
        numerator=800,
        denominator=1,
    )
    record_point(
        settings,
        "report.coverage",
        0.5,
        scope="run",
        scope_id="r1",
        run_id="r1",
        numerator=1,
        denominator=0,
    )
    points = load_points(settings, "r1")
    assert any(point["metric_id"] == "report.words" and point["value"] == 800 for point in points)
    coverage = next(point for point in points if point["metric_id"] == "report.coverage")
    assert coverage["value"] is None
    assert summarize_points(points)["report.words"] == 800


def test_report_collector_and_spans(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    seed_definitions(settings)
    run_graph(settings, "ai-agents", run_id="metric-run", focus_hint="tool use")
    collect_report_points(settings, "metric-run")
    points = load_points(settings, "metric-run")
    summary = summarize_points(points)
    assert summary["report.words"] > 0
    assert summary["claim.citation_coverage"] == 1.0

    span_id = record_span(
        settings, run_id="metric-run", name="report", status="ok", duration_ms=12
    )
    assert span_id


def test_compare_and_score() -> None:
    baseline = {"report.coverage": 0.5, "rag.faithfulness": 0.8, "report.words": 700}
    candidate = {"report.coverage": 0.7, "rag.faithfulness": 0.8, "report.words": 900}
    comparison = compare_summaries(baseline, candidate)
    assert "report.coverage" in comparison.improvements
    assert score_summary(candidate) > score_summary(baseline)


def test_rule_evaluator_claim_purity() -> None:
    evaluator = RuleEvaluator()
    result = evaluator.claims(
        [
            {
                "text": "tool use improves success",
                "citations": [{"paper_id": "P1"}],
            },
            {"text": "published at ACL 2024", "citations": []},
        ]
    )
    assert result.metrics["claim.purity"] == 0.5
    assert result.metrics["claim.citation_coverage"] == 0.5


def test_promotion_policy_and_experiment_record(tmp_path: Path) -> None:
    baseline = {"report.coverage": 0.5, "rag.faithfulness": 0.8}
    candidate = {"report.coverage": 0.7, "rag.faithfulness": 0.8}
    comparison = compare_summaries(baseline, candidate)
    promote, reasons = decide_promotion(comparison, score_delta=0.1)
    assert promote is True
    assert reasons == []

    settings = prepare(tmp_path)
    experiment_id = save_experiment(
        settings,
        Experiment(name="test", config={"x": 1}, dataset="fixture", status="promoted"),
    )
    assert experiment_id

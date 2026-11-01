"""M5-P01: scorecards, hard gates, confidence, directions."""

from __future__ import annotations

from lit_agent_v2.metrics.scorecard import (
    JudgeScores,
    build_scorecard,
    normalize_metric,
)

METRICS = {
    "search.coverage": 0.95,
    "search.duplicate_rate": 0.02,
    "metadata.completeness": 0.95,
    "metadata.authors_rate": 0.95,
    "fulltext.available_ratio": 0.5,
    "card.quote_verbatim_rate": 1.0,
    "claim.purity": 1.0,
    "claim.citation_coverage": 1.0,
    "cluster.count": 5,
    "cluster.min_size": 3,
    "cluster.outlier_rate": 0.1,
    "direction.max_share": 0.4,
    "report.words": 1500,
    "report.claim_coverage": 0.9,
    "report.count_reconciliation": 1.0,
    "report.duplicate_claim_rate": 0.0,
    "report.citation_coverage": 1.0,
    "report.uncited_facts": 0,
}


def test_scorecard_accepts_clean_run() -> None:
    card = build_scorecard(
        run_id="r1",
        report_id="p1",
        state="complete",
        metrics=METRICS,
        sample_size=20,
        judge=JudgeScores(5, 5, 5, 5, 5, 5),
        directions=[{"direction_id": "D1", "score": 0.9, "size": 10}],
    )
    assert card.hard_fail == []
    assert card.total == 1.0
    assert card.confidence == 1.0
    assert card.verdict == "accept"
    assert card.directions[0].direction_id == "D1"


def test_hard_gate_caps_total() -> None:
    metrics = {**METRICS, "report.citation_coverage": 0.8}
    card = build_scorecard(
        run_id="r1", report_id="p1", state="complete", metrics=metrics, sample_size=20
    )
    assert "report.citation_coverage" in card.hard_fail
    assert card.total <= 0.5
    assert card.verdict == "fail"


def test_confidence_scales_total() -> None:
    card = build_scorecard(
        run_id="r1", report_id="p1", state="complete", metrics=METRICS, sample_size=10
    )
    assert card.confidence == 0.5
    assert card.total == 0.5


def test_normalize_metric_directions() -> None:
    assert normalize_metric("search.coverage", 1.0) == 1.0
    assert normalize_metric("search.duplicate_rate", 0.0) == 1.0
    assert normalize_metric("cluster.count", 5) == 1.0
    assert normalize_metric("report.words", 400) < 1.0

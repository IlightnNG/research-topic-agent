"""Report/run evaluation summary and baseline comparison (S17)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["compare_summaries", "score_summary", "summarize_points"]


@dataclass
class Comparison:
    deltas: dict[str, float]
    regressions: list[str]
    improvements: list[str]
    hard_fail: list[str]


def summarize_points(points: list[dict[str, Any]]) -> dict[str, float]:
    """Latest value per metric_id. NULL values are omitted (not converted to 0)."""
    latest: dict[str, tuple[str, float]] = {}
    for point in points:
        value = point.get("value")
        if value is None:
            continue
        ts = str(point.get("ts") or "")
        metric = str(point.get("metric_id") or "")
        if metric and (metric not in latest or ts >= latest[metric][0]):
            latest[metric] = (ts, float(value))
    return {key: value for key, (_ts, value) in latest.items()}


def score_summary(summary: dict[str, float]) -> float:
    weights = {
        "rag.faithfulness": 0.25,
        "rag.citation_precision": 0.2,
        "report.coverage": 0.2,
        "search.precision_at_k": 0.2,
        "report.words": 0.05,
        "report.fallback_rate": 0.1,
    }
    total = 0.0
    weight_sum = 0.0
    for key, weight in weights.items():
        if key not in summary:
            continue
        value = summary[key]
        if key == "report.words":
            value = 1.0 if 600 <= value <= 1200 else 0.5
        total += weight * value
        weight_sum += weight
    return round(total / weight_sum, 4) if weight_sum else 0.0


def compare_summaries(
    baseline: dict[str, float],
    candidate: dict[str, float],
    *,
    threshold: float = 0.02,
    hard_metrics: tuple[str, ...] = ("rag.citation_coverage", "claim.purity"),
) -> Comparison:
    deltas: dict[str, float] = {}
    regressions: list[str] = []
    improvements: list[str] = []
    for key, value in candidate.items():
        if key not in baseline:
            continue
        delta = round(value - baseline[key], 4)
        deltas[key] = delta
        if key == "report.fallback_rate":
            delta = -delta
        if delta <= -threshold:
            regressions.append(key)
        elif delta >= threshold:
            improvements.append(key)
    hard_fail = [key for key in hard_metrics if candidate.get(key, 1.0) < baseline.get(key, 0.0)]
    return Comparison(deltas, regressions, improvements, hard_fail)

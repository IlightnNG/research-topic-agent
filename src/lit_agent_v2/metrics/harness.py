"""Metric test harness."""

from __future__ import annotations

from lit_agent_v2.metrics.gates import check_metric

__all__ = ["assert_metric_between", "summarize_metrics"]


def summarize_metrics(points: list[dict]) -> dict[str, float]:
    latest: dict[str, tuple[str, float]] = {}
    for point in points:
        if point.get("value") is None:
            continue
        key = str(point.get("metric_id") or "")
        ts = str(point.get("ts") or "")
        if key not in latest or ts >= latest[key][0]:
            latest[key] = (ts, float(point["value"]))
    return {key: value for key, (_ts, value) in latest.items()}


def assert_metric_between(metric_id: str, value: float, low: float, high: float) -> None:
    if not low <= value <= high:
        raise AssertionError(f"{metric_id}={value} not in [{low}, {high}]")
    problems = check_metric(metric_id, value)
    if problems:
        raise AssertionError("; ".join(problems))

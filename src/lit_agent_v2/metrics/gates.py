"""Metric gates for v2 slices."""

from __future__ import annotations

from lit_agent_v2.metrics.catalog import CATALOG

__all__ = ["MetricGateError", "check_metric"]


class MetricGateError(RuntimeError):
    pass


def check_metric(metric_id: str, value: float | None, *, sample_size: int = 0) -> list[str]:
    spec = CATALOG[metric_id]
    if value is None:
        return [f"{metric_id}: NULL"]
    if sample_size < spec.sample_min:
        return [f"{metric_id}: sample {sample_size} < {spec.sample_min}"]
    problems: list[str] = []
    if spec.direction == "higher_better" and spec.min_value is not None and value < spec.min_value:
        problems.append(f"{metric_id}: {value} < {spec.min_value}")
    if spec.direction == "lower_better" and spec.max_value is not None and value > spec.max_value:
        problems.append(f"{metric_id}: {value} > {spec.max_value}")
    if spec.direction == "in_range":
        if spec.min_value is not None and value < spec.min_value:
            problems.append(f"{metric_id}: {value} < {spec.min_value}")
        if spec.max_value is not None and value > spec.max_value:
            problems.append(f"{metric_id}: {value} > {spec.max_value}")
    return problems


def assert_metric(metric_id: str, value: float | None, *, sample_size: int = 0) -> None:
    problems = check_metric(metric_id, value, sample_size=sample_size)
    if problems:
        raise MetricGateError("; ".join(problems))

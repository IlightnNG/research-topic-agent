"""M5-P02: judge-human calibration metrics."""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass, field

__all__ = [
    "CalibrationReport",
    "CalibrationSample",
    "calibrate",
    "cohen_kappa",
    "mae",
    "pearson",
    "spearman",
]


@dataclass(frozen=True)
class CalibrationSample:
    dimension: str
    human: float
    judge: float
    human_verdict: str | None = None
    judge_verdict: str | None = None


@dataclass
class CalibrationReport:
    pearson: float
    spearman: float
    mae: float
    kappa: float
    samples: int
    passed: bool
    dimensions: dict[str, dict[str, float]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "pearson": self.pearson,
            "spearman": self.spearman,
            "mae": self.mae,
            "kappa": self.kappa,
            "samples": self.samples,
            "passed": self.passed,
            "dimensions": self.dimensions,
        }


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) != len(ys) or len(xs) < 2:
        return 0.0
    mx, my = _mean(xs), _mean(ys)
    numerator = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False))
    denom = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return numerator / denom if denom else 0.0


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda index: values[index])
    ranks = [0.0] * len(values)
    index = 0
    while index < len(order):
        end = index
        while end + 1 < len(order) and values[order[end + 1]] == values[order[index]]:
            end += 1
        average = (index + end) / 2 + 1
        for position in range(index, end + 1):
            ranks[order[position]] = average
        index = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float:
    return pearson(_rank(xs), _rank(ys))


def mae(xs: list[float], ys: list[float]) -> float:
    if not xs:
        return 0.0
    return sum(abs(x - y) for x, y in zip(xs, ys, strict=False)) / len(xs)


def cohen_kappa(human: list[str], judge: list[str]) -> float:
    if len(human) != len(judge) or not human:
        return 0.0
    labels = sorted(set(human) | set(judge))
    total = len(human)
    observed = sum(1 for a, b in zip(human, judge, strict=False) if a == b) / total
    expected = sum(
        (human.count(label) / total) * (judge.count(label) / total)
        for label in labels
    )
    if expected >= 1.0:
        return 1.0 if observed >= 1.0 else 0.0
    return (observed - expected) / (1 - expected)


def calibrate(
    samples: Iterable[CalibrationSample],
    *,
    min_samples: int = 20,
    min_correlation: float = 0.6,
    max_mae: float = 0.5,
    min_kappa: float = 0.6,
) -> CalibrationReport:
    items = list(samples)
    if len(items) < min_samples:
        return CalibrationReport(0.0, 0.0, 0.0, 0.0, len(items), False, {})
    xs = [item.human for item in items]
    ys = [item.judge for item in items]
    dimensions: dict[str, dict[str, float]] = {}
    for dimension in sorted({item.dimension for item in items}):
        subset = [item for item in items if item.dimension == dimension]
        dimensions[dimension] = {
            "pearson": round(pearson([i.human for i in subset], [i.judge for i in subset]), 4),
            "spearman": round(spearman([i.human for i in subset], [i.judge for i in subset]), 4),
            "mae": round(mae([i.human for i in subset], [i.judge for i in subset]), 4),
            "samples": float(len(subset)),
        }
    labels = [item for item in items if item.human_verdict and item.judge_verdict]
    kappa = (
        cohen_kappa(
            [str(item.human_verdict) for item in labels],
            [str(item.judge_verdict) for item in labels],
        )
        if labels
        else 0.0
    )
    p = pearson(xs, ys)
    s = spearman(xs, ys)
    error = mae(xs, ys)
    passed = (
        len(items) >= min_samples
        and p >= min_correlation
        and s >= min_correlation
        and error <= max_mae
        and (not labels or kappa >= min_kappa)
    )
    return CalibrationReport(
        pearson=round(p, 4),
        spearman=round(s, 4),
        mae=round(error, 4),
        kappa=round(kappa, 4),
        samples=len(items),
        passed=passed,
        dimensions=dimensions,
    )

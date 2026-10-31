"""Rule-based evaluation for v2 S7."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from lit_agent_v2.evaluation.dataset import EvalCase


class DirectionLike(Protocol):
    paper_ids: list[str]


class MapLike(Protocol):
    directions: list[DirectionLike]
    min_size: int

__all__ = ["EvalResult", "direction_f1", "evaluate"]


@dataclass
class EvalResult:
    metrics: dict[str, float] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def _ids(groups: list[list[str]]) -> list[set[str]]:
    return [set(group) for group in groups if group]


def direction_f1(pred: MapLike, gold: list[list[str]]) -> float:
    predicted = [set(item.paper_ids) for item in pred.directions]
    expected = _ids(gold)
    if not predicted or not expected:
        return 0.0
    matched: set[int] = set()
    correct = 0
    for group in predicted:
        best_index = max(
            (index for index in range(len(expected)) if index not in matched),
            key=lambda index: len(group & expected[index]),
            default=None,
        )
        if best_index is None:
            continue
        if len(group & expected[best_index]) > 0:
            matched.add(best_index)
            correct += 1
    precision = correct / len(predicted) if predicted else 0.0
    recall = correct / len(expected) if expected else 0.0
    return round(2 * precision * recall / (precision + recall), 4) if precision + recall else 0.0


def evaluate(*, case: EvalCase, mapping: MapLike, words: int, citations: float) -> EvalResult:
    metrics = {
        "directions.f1": direction_f1(mapping, case.gold_directions),
        "report.words": float(words),
        "report.citation_coverage": citations,
        "cluster.count": float(len(mapping.directions)),
        "cluster.min_size": float(mapping.min_size),
    }
    problems: list[str] = []
    if metrics["directions.f1"] == 0 and case.gold_directions:
        problems.append("no gold direction matched")
    if not 1500 <= words <= 3000:
        problems.append(f"words {words} out of range")
    if citations < 1.0:
        problems.append("citation coverage < 1")
    return EvalResult(metrics, problems)


def match_claims(text: str, gold_claims: list[str]) -> float:
    if not gold_claims:
        return 0.0
    normalized = re.sub(r"\s+", " ", text.lower())
    hits = sum(1 for claim in gold_claims if re.sub(r"\s+", " ", claim.lower()) in normalized)
    return hits / len(gold_claims)

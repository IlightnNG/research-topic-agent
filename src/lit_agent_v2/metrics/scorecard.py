"""M5-P01: module scorecard, direction scores, hard gates, confidence."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.metrics.catalog import CATALOG
from lit_agent_v2.metrics.harness import summarize_metrics

__all__ = [
    "DirectionScore",
    "build_scorecard_from_points",
    "JudgeScores",
    "ModuleScore",
    "ScoreCard",
    "build_scorecard",
    "normalize_metric",
]

MODULE_WEIGHTS: dict[str, float] = {
    "source": 0.10,
    "evidence": 0.15,
    "claims": 0.15,
    "map": 0.15,
    "writing": 0.20,
    "cross": 0.10,
    "grounding": 0.10,
    "process": 0.05,
}

MODULE_METRICS: dict[str, tuple[str, ...]] = {
    "source": ("search.coverage", "search.duplicate_rate", "metadata.completeness", "metadata.authors_rate"),
    "evidence": ("fulltext.available_ratio", "card.quote_verbatim_rate"),
    "claims": ("claim.purity", "claim.citation_coverage"),
    "map": ("cluster.count", "cluster.min_size", "cluster.outlier_rate", "direction.max_share"),
    "writing": (
        "report.words",
        "report.claim_coverage",
        "report.count_reconciliation",
        "report.duplicate_claim_rate",
    ),
    "cross": (),
    "grounding": ("report.citation_coverage", "report.uncited_facts"),
    "process": (),
}


@dataclass
class JudgeScores:
    relevance: float = 0.0
    coverage: float = 0.0
    grounding: float = 0.0
    synthesis: float = 0.0
    readability: float = 0.0
    actionability: float = 0.0

    @property
    def normalized(self) -> dict[str, float]:
        return {
            key: max(0.0, min(1.0, value / 5.0))
            for key, value in self.__dict__.items()
        }


@dataclass
class ModuleScore:
    name: str
    score: float | None
    metrics: dict[str, float] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    judge: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "metrics": self.metrics,
            "missing": self.missing,
            "judge": self.judge,
        }


@dataclass
class DirectionScore:
    direction_id: str
    score: float
    size: int
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction_id": self.direction_id,
            "score": self.score,
            "size": self.size,
            "metrics": self.metrics,
        }


@dataclass
class ScoreCard:
    run_id: str
    report_id: str
    state: str
    modules: dict[str, ModuleScore]
    directions: list[DirectionScore]
    total: float
    confidence: float
    hard_fail: list[str]
    missing: list[str]
    verdict: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "report_id": self.report_id,
            "state": self.state,
            "modules": {name: score.to_dict() for name, score in self.modules.items()},
            "directions": [score.to_dict() for score in self.directions],
            "total": self.total,
            "confidence": self.confidence,
            "hard_fail": self.hard_fail,
            "missing": self.missing,
            "verdict": self.verdict,
        }


def normalize_metric(metric_id: str, value: float | None) -> float | None:
    if value is None:
        return None
    spec = CATALOG.get(metric_id)
    if spec is None:
        return max(0.0, min(1.0, float(value)))
    number = float(value)
    if spec.direction == "higher_better":
        target = spec.min_value if spec.min_value not in (None, 0) else 1.0
        return max(0.0, min(1.0, number / float(target)))
    if spec.direction == "lower_better":
        ceiling = spec.max_value if spec.max_value not in (None, 0) else 0.0
        if number <= ceiling:
            return 1.0
        return max(0.0, min(1.0, ceiling / number)) if number else 1.0
    low = spec.min_value if spec.min_value is not None else number
    high = spec.max_value if spec.max_value is not None else number
    if low <= number <= high:
        return 1.0
    if number < low:
        return max(0.0, 1.0 - (low - number) / max(1.0, low))
    return max(0.0, 1.0 - (number - high) / max(1.0, high))


def _module_score(
    name: str,
    metrics: dict[str, float],
    judge: JudgeScores | None,
) -> ModuleScore:
    available: dict[str, float] = {}
    missing: list[str] = []
    for metric_id in MODULE_METRICS[name]:
        if metric_id in metrics and metrics[metric_id] is not None:
            normalized = normalize_metric(metric_id, metrics[metric_id])
            if normalized is not None:
                available[metric_id] = round(normalized, 4)
        else:
            missing.append(metric_id)
    judge_score: float | None = None
    if judge is not None:
        normalized_judge = judge.normalized
        if name == "writing":
            judge_score = round(
                sum(normalized_judge[key] for key in ("relevance", "coverage", "readability")) / 3,
                4,
            )
        elif name == "cross":
            judge_score = normalized_judge["synthesis"]
        elif name == "grounding":
            judge_score = normalized_judge["grounding"]
    if judge_score is not None and available:
        score = 0.5 * (sum(available.values()) / len(available)) + 0.5 * judge_score
    elif judge_score is not None:
        score = judge_score
    elif available:
        score = sum(available.values()) / len(available)
    else:
        score = None
    return ModuleScore(name, round(score, 4) if score is not None else None, available, missing, judge_score)


def _hard_failures(metrics: dict[str, float]) -> list[str]:
    failures: list[str] = []
    for spec in CATALOG.values():
        if not spec.hard:
            continue
        if spec.metric_id not in metrics or metrics[spec.metric_id] is None:
            failures.append(f"{spec.metric_id}:missing")
            continue
        value = float(metrics[spec.metric_id])
        if spec.direction == "higher_better":
            if spec.min_value is not None and value < spec.min_value:
                failures.append(spec.metric_id)
        elif spec.direction == "lower_better":
            if spec.max_value is not None and value > spec.max_value:
                failures.append(spec.metric_id)
        elif spec.direction == "in_range":
            below = spec.min_value is not None and value < spec.min_value
            above = spec.max_value is not None and value > spec.max_value
            if below or above:
                failures.append(spec.metric_id)
    return failures


def build_scorecard(
    *,
    run_id: str,
    report_id: str,
    state: str,
    metrics: dict[str, float],
    sample_size: int = 0,
    judge: JudgeScores | None = None,
    directions: list[dict[str, Any]] | None = None,
) -> ScoreCard:
    modules = {
        name: _module_score(name, metrics, judge)
        for name in MODULE_WEIGHTS
    }
    hard_fail = _hard_failures(metrics)
    available_weights = sum(
        MODULE_WEIGHTS[name] for name, score in modules.items() if score.score is not None
    )
    if available_weights:
        total = sum(
            MODULE_WEIGHTS[name] * (score.score or 0.0)
            for name, score in modules.items()
            if score.score is not None
        ) / available_weights
    else:
        total = 0.0
    if hard_fail:
        total = min(total, 0.5)
    confidence = min(1.0, sample_size / 20) if sample_size else 0.0
    direction_scores: list[DirectionScore] = []
    for item in directions or []:
        raw = item.get("score")
        direction_scores.append(
            DirectionScore(
                direction_id=str(item.get("direction_id") or ""),
                score=round(float(raw if raw is not None else 0.0), 4),
                size=int(item.get("size") or 0),
                metrics=dict(item.get("metrics") or {}),
            )
        )
    total = round(total * confidence, 4)
    verdict = "fail" if hard_fail else ("accept" if total >= 0.7 else "repair")
    return ScoreCard(
        run_id=run_id,
        report_id=report_id,
        state=state,
        modules=modules,
        directions=direction_scores,
        total=total,
        confidence=round(confidence, 4),
        hard_fail=hard_fail,
        missing=[f"{name}:{metric}" for name, score in modules.items() for metric in score.missing],
        verdict=verdict,
    )


def build_scorecard_from_points(
    *,
    run_id: str,
    report_id: str,
    state: str,
    points: list[dict],
    sample_size: int = 0,
    judge: JudgeScores | None = None,
    directions: list[dict] | None = None,
) -> ScoreCard:
    metrics = summarize_metrics(points)
    return build_scorecard(
        run_id=run_id,
        report_id=report_id,
        state=state,
        metrics=metrics,
        sample_size=sample_size,
        judge=judge,
        directions=directions,
    )

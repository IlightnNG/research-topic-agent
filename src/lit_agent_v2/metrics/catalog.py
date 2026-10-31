"""Metric specs for v2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = ["CATALOG", "MetricSpec"]


@dataclass(frozen=True)
class MetricSpec:
    metric_id: str
    version: str
    stage: str
    unit: str
    direction: Literal["higher_better", "lower_better", "in_range"]
    formula: str
    hard: bool = False
    min_value: float | None = None
    max_value: float | None = None
    sample_min: int = 0


def _m(
    metric_id: str,
    stage: str,
    unit: str,
    direction: Literal["higher_better", "lower_better", "in_range"],
    formula: str,
    *,
    hard: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
    sample_min: int = 0,
) -> MetricSpec:
    return MetricSpec(
        metric_id, "1.0", stage, unit, direction, formula, hard, min_value, max_value, sample_min
    )


CATALOG: dict[str, MetricSpec] = {
    "search.coverage": _m(
        "search.coverage", "source", "ratio", "higher_better", "selected / requested", hard=True, min_value=0.8
    ),
    "search.duplicate_rate": _m(
        "search.duplicate_rate", "source", "ratio", "lower_better", "duplicates / retrieved", hard=True, max_value=0.1
    ),
    "metadata.completeness": _m(
        "metadata.completeness", "source", "ratio", "higher_better", "complete_metadata / papers", min_value=0.9
    ),
    "metadata.authors_rate": _m(
        "metadata.authors_rate", "source", "ratio", "higher_better", "papers_with_authors / papers", min_value=0.9
    ),
    "fulltext.available_ratio": _m(
        "fulltext.available_ratio", "evidence", "ratio", "higher_better", "fulltext / papers", min_value=0.3
    ),
    "card.quote_verbatim_rate": _m(
        "card.quote_verbatim_rate", "evidence", "ratio", "higher_better", "verbatim_quotes / quotes", hard=True, min_value=1.0
    ),
    "claim.purity": _m(
        "claim.purity", "evidence", "ratio", "higher_better", "research_claims / claims", hard=True, min_value=0.98
    ),
    "claim.citation_coverage": _m(
        "claim.citation_coverage", "evidence", "ratio", "higher_better", "cited_claims / claims", hard=True, min_value=1.0
    ),
    "cluster.count": _m(
        "cluster.count", "map", "count", "in_range", "policy_for(n).target_directions", min_value=3, max_value=12
    ),
    "cluster.min_size": _m(
        "cluster.min_size", "map", "count", "higher_better", "min(direction.papers)", min_value=3
    ),
    "cluster.outlier_rate": _m(
        "cluster.outlier_rate", "map", "ratio", "lower_better", "outliers / papers", max_value=0.2
    ),
    "report.words": _m(
        "report.words", "write", "count", "in_range", "policy_for(n).target_words", min_value=500, max_value=6000
    ),
    "report.claim_coverage": _m(
        "report.claim_coverage", "write", "ratio", "higher_better", "displayed_claims / claims", min_value=0.8
    ),
    "direction.max_share": _m(
        "direction.max_share", "map", "ratio", "lower_better", "max(direction.papers) / papers", max_value=0.6
    ),
    "report.count_reconciliation": _m(
        "report.count_reconciliation", "write", "ratio", "higher_better", "displayed_claims / claims", hard=True, min_value=1.0
    ),
    "report.duplicate_claim_rate": _m(
        "report.duplicate_claim_rate", "write", "ratio", "lower_better", "duplicate_claim_refs / claim_refs", max_value=0.1
    ),
    "report.citation_coverage": _m(
        "report.citation_coverage", "write", "ratio", "higher_better", "cited_facts / facts", hard=True, min_value=1.0
    ),
    "report.uncited_facts": _m(
        "report.uncited_facts", "write", "count", "lower_better", "uncited_facts", hard=True, max_value=0
    ),
}

"""Standard metric catalog (Phase 3.4 / S16)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["CATALOG", "MetricDef", "get_definition"]


@dataclass(frozen=True)
class MetricDef:
    metric_id: str
    version: str
    domain: str
    unit: str
    direction: str
    formula: str
    target: dict[str, Any] | None = None


def _m(metric_id: str, domain: str, unit: str, direction: str, formula: str, target=None) -> MetricDef:
    return MetricDef(metric_id, "1.0", domain, unit, direction, formula, target)


CATALOG: dict[str, MetricDef] = {
    # Search / RAG
    "search.recall_at_k": _m("search.recall_at_k", "search", "ratio", "higher_better", "relevant_in_top_k / relevant_total"),
    "search.precision_at_k": _m("search.precision_at_k", "search", "ratio", "higher_better", "relevant_in_top_k / k"),
    "search.topic_relevance": _m("search.topic_relevance", "search", "ratio", "higher_better", "relevant_papers / sampled_papers"),
    "search.coverage": _m("search.coverage", "search", "count", "in_range", "papers_selected", {"min": 80, "max": 120}),
    "cluster.count": _m("cluster.count", "cluster", "count", "in_range", "len(directions)", {"min": 5, "max": 8}),
    "cluster.min_size": _m("cluster.min_size", "cluster", "count", "higher_better", "min(direction.size)"),
    "cluster.outlier_rate": _m("cluster.outlier_rate", "cluster", "ratio", "lower_better", "outliers / papers"),
    "cluster.coherence": _m("cluster.coherence", "cluster", "ratio", "higher_better", "claim_links / paper_slots"),
    "report.comparison_completeness": _m("report.comparison_completeness", "report", "ratio", "higher_better", "comparison_sections / 1"),
    "rag.context_precision": _m("rag.context_precision", "rag", "ratio", "higher_better", "relevant_chunks / context_chunks"),
    "rag.context_recall": _m("rag.context_recall", "rag", "ratio", "higher_better", "covered_gold / gold_total"),
    "rag.faithfulness": _m("rag.faithfulness", "rag", "ratio", "higher_better", "supported_sentences / sentences"),
    "rag.citation_precision": _m("rag.citation_precision", "rag", "ratio", "higher_better", "valid_citations / citations"),
    "rag.citation_coverage": _m("rag.citation_coverage", "rag", "ratio", "higher_better", "cited_claims / claims"),
    # Claim / report
    "card.quote_verbatim_rate": _m("card.quote_verbatim_rate", "card", "ratio", "higher_better", "verbatim_quotes / quotes"),
    "claim.purity": _m("claim.purity", "claim", "ratio", "higher_better", "research_claims / claims"),
    "claim.citation_coverage": _m("claim.citation_coverage", "claim", "ratio", "higher_better", "cited_claims / claims"),
    "report.words": _m("report.words", "report", "count", "in_range", "word_count", {"min": 600, "max": 1200}),
    "report.sections": _m("report.sections", "report", "count", "in_range", "len(sections)", {"min": 4, "max": 6}),
    "report.coverage": _m("report.coverage", "report", "ratio", "higher_better", "papers_with_claims / papers"),
    "report.fallback_rate": _m("report.fallback_rate", "report", "ratio", "lower_better", "fallbacks / directions"),
    "report.thin": _m("report.thin", "report", "count", "lower_better", "1 if thin else 0"),
    "report.cache_hit_rate": _m("report.cache_hit_rate", "report", "ratio", "higher_better", "cache_hits / llm_calls"),
    # Process
    "stage.duration_ms": _m("stage.duration_ms", "process", "ms", "lower_better", "end - start"),
    "llm.failures": _m("llm.failures", "process", "count", "lower_better", "failed_calls"),
}


def get_definition(metric_id: str) -> MetricDef:
    if metric_id not in CATALOG:
        raise KeyError(metric_id)
    return CATALOG[metric_id]

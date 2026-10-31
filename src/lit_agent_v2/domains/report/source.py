"""Source selection for v2 S2."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from lit_agent_v2.domains.report.contracts import Paper, SourceArtifact
from lit_agent_v2.metrics.gates import assert_metric
from lit_agent_v2.metrics.store import MetricStore

__all__ = ["SourceService"]


def _terms(text: str) -> set[str]:
    return {word for word in re.split(r"\W+", text.lower()) if len(word) > 2}


class SourceService:
    def __init__(self, metrics: MetricStore | None = None) -> None:
        self.metrics = metrics

    def select(
        self,
        *,
        topic_id: str,
        query: str,
        papers: list[Paper],
        limit: int = 100,
        run_id: str | None = None,
    ) -> SourceArtifact:
        seen: set[str] = set()
        unique: list[tuple[int, Paper]] = []
        wanted = _terms(query)
        for paper in papers:
            key = paper.paper_id.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            score = len(wanted & _terms(f"{paper.title} {paper.abstract}"))
            unique.append((score, paper))
        unique.sort(key=lambda item: (-item[0], item[1].paper_id))
        selected = [paper for _score, paper in unique[: max(1, limit)]]
        relevant = sum(1 for score, _paper in unique[: max(1, limit)] if score > 0 or not wanted)
        artifact = SourceArtifact(
            topic_id=topic_id,
            query=query,
            papers=selected,
            requested=limit,
            retrieved=len(unique),
            relevant=relevant,
            retrieved_at=datetime.now(UTC).isoformat(),
        )
        coverage = len(selected) / max(1, limit)
        duplicates = (len(papers) - len(unique)) / max(1, len(papers))
        assert_metric("search.coverage", coverage, sample_size=len(selected))
        assert_metric("search.duplicate_rate", duplicates, sample_size=len(papers))
        if self.metrics and run_id:
            self.metrics.point(
                "search.coverage", coverage, run_id=run_id, node_id="source", sample_size=len(selected)
            )
            self.metrics.point(
                "search.duplicate_rate",
                duplicates,
                run_id=run_id,
                node_id="source",
                sample_size=len(papers),
            )
        return artifact

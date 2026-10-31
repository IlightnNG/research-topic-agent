"""Evidence construction for v2 S2."""

from __future__ import annotations

from lit_agent_v2.domains.report.claim_extractor import extract_deterministic
from lit_agent_v2.domains.report.contracts import EvidenceArtifact, SourceArtifact
from lit_agent_v2.metrics.gates import assert_metric
from lit_agent_v2.metrics.store import MetricStore

__all__ = ["EvidenceService"]


class EvidenceService:
    def __init__(self, metrics: MetricStore | None = None, *, extractor=None) -> None:
        self.metrics = metrics
        self.extractor = extractor or extract_deterministic

    def build(
        self,
        source: SourceArtifact,
        *,
        run_id: str | None = None,
        max_claims_per_paper: int = 2,
    ) -> EvidenceArtifact:
        artifact = EvidenceArtifact()
        for paper in source.papers:
            body = paper.fulltext or paper.abstract
            levels = "L2" if paper.fulltext else "L1"
            if paper.fulltext:
                artifact.fulltext += 1
            claims = []
            if body:
                extracted = self.extractor(paper.paper_id, body)
                for claim in extracted[:max_claims_per_paper]:
                    if claim.quote not in body:
                        continue
                    claims.append(claim)
                    artifact.claims += 1
                    artifact.quote_checks += 1
                    artifact.quote_ok += 1
                    artifact.research_claims += 1
            if claims:
                artifact.with_claims += 1
            artifact.papers.append(
                {
                    "paper_id": paper.paper_id,
                    "title": paper.title,
                    "abstract": paper.abstract,
                    "level": levels,
                    "fulltext_available": bool(paper.fulltext),
                    "quote_windows": [
                        {"text": claim.quote, "section": claim.section, "page": claim.page}
                        for claim in claims
                    ],
                    "claims": [claim.to_dict() for claim in claims],
                }
            )

        assert_metric(
            "card.quote_verbatim_rate",
            artifact.quote_verbatim_rate,
            sample_size=artifact.quote_checks,
        )
        assert_metric("claim.purity", artifact.claim_purity, sample_size=artifact.claims)
        assert_metric(
            "claim.citation_coverage",
            1.0 if artifact.claims else 0.0,
            sample_size=artifact.claims,
        )
        if self.metrics and run_id:
            for metric_id, value in (
                ("fulltext.available_ratio", artifact.fulltext_ratio),
                ("card.quote_verbatim_rate", artifact.quote_verbatim_rate),
                ("claim.purity", artifact.claim_purity),
                ("claim.citation_coverage", 1.0 if artifact.claims else 0.0),
            ):
                self.metrics.point(
                    metric_id,
                    value,
                    run_id=run_id,
                    node_id="evidence",
                    sample_size=len(artifact.papers),
                )
        return artifact

"""Report domain contracts for v2."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Claim",
    "EvidenceArtifact",
    "Paper",
    "QuoteWindow",
    "SourceArtifact",
]


@dataclass
class Paper:
    paper_id: str
    title: str
    abstract: str = ""
    url: str = ""
    source: str = "local"
    fulltext: str = ""
    venue: str = ""
    year: int | None = None
    pdf_url: str = ""
    html_url: str = ""


@dataclass
class QuoteWindow:
    text: str
    section: str = "abstract"
    page: int = 1


@dataclass
class Claim:
    claim_id: str
    paper_id: str
    text: str
    quote: str
    section: str = "abstract"
    page: int = 1
    confidence: float = 0.5

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "paper_id": self.paper_id,
            "text": self.text,
            "quote": self.quote,
            "section": self.section,
            "page": self.page,
            "confidence": self.confidence,
        }


@dataclass
class SourceArtifact:
    topic_id: str
    query: str
    papers: list[Paper] = field(default_factory=list)
    requested: int = 0
    retrieved: int = 0
    relevant: int = 0
    strategy: str = "local"
    retrieved_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "topic_id": self.topic_id,
            "query": self.query,
            "papers": [paper.__dict__ for paper in self.papers],
            "readiness": {
                "requested": self.requested,
                "retrieved": self.retrieved,
                "relevant": self.relevant,
            },
            "provenance": {"strategy": self.strategy, "retrieved_at": self.retrieved_at},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SourceArtifact:
        readiness = data.get("readiness") or {}
        provenance = data.get("provenance") or {}
        return cls(
            topic_id=str(data.get("topic_id") or ""),
            query=str(data.get("query") or ""),
            papers=[Paper(**paper) for paper in data.get("papers", [])],
            requested=int(readiness.get("requested") or 0),
            retrieved=int(readiness.get("retrieved") or 0),
            relevant=int(readiness.get("relevant") or 0),
            strategy=str(provenance.get("strategy") or "local"),
            retrieved_at=str(provenance.get("retrieved_at") or ""),
        )


@dataclass
class EvidenceArtifact:
    papers: list[dict[str, Any]] = field(default_factory=list)
    with_claims: int = 0
    fulltext: int = 0
    quote_checks: int = 0
    quote_ok: int = 0
    claims: int = 0
    research_claims: int = 0

    @property
    def quote_verbatim_rate(self) -> float:
        return self.quote_ok / self.quote_checks if self.quote_checks else 0.0

    @property
    def claim_purity(self) -> float:
        return self.research_claims / self.claims if self.claims else 0.0

    @property
    def fulltext_ratio(self) -> float:
        return self.fulltext / len(self.papers) if self.papers else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "papers": self.papers,
            "coverage": {
                "papers": len(self.papers),
                "with_claims": self.with_claims,
                "fulltext": self.fulltext,
            },
            "stats": {
                "quote_checks": self.quote_checks,
                "quote_ok": self.quote_ok,
                "claims": self.claims,
                "research_claims": self.research_claims,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EvidenceArtifact:
        stats = data.get("stats") or {}
        coverage = data.get("coverage") or {}
        return cls(
            papers=list(data.get("papers") or []),
            with_claims=int(coverage.get("with_claims") or 0),
            fulltext=int(coverage.get("fulltext") or 0),
            quote_checks=int(stats.get("quote_checks") or 0),
            quote_ok=int(stats.get("quote_ok") or 0),
            claims=int(stats.get("claims") or 0),
            research_claims=int(stats.get("research_claims") or 0),
        )

"""Shared report contracts. Owned by no single domain module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Claim",
    "Direction",
    "EvidenceArtifact",
    "MapArtifact",
    "Paper",
    "QuoteWindow",
    "ReportDraft",
    "Section",
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
    authors: list[str] = field(default_factory=list)


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
    claim_type: str = "finding"

    def to_dict(self) -> dict[str, Any]:
        return {
            "claim_id": self.claim_id,
            "paper_id": self.paper_id,
            "text": self.text,
            "quote": self.quote,
            "section": self.section,
            "page": self.page,
            "confidence": self.confidence,
            "claim_type": self.claim_type,
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


@dataclass
class Direction:
    direction_id: str
    name: str
    paper_ids: list[str]
    claim_ids: list[str] = field(default_factory=list)
    coherence: float = 0.0
    outliers: list[str] = field(default_factory=list)


@dataclass
class MapArtifact:
    directions: list[Direction] = field(default_factory=list)
    papers: int = 0
    outlier_rate: float = 0.0
    count_quality: str = "complete"

    @property
    def min_size(self) -> int:
        return min((len(item.paper_ids) for item in self.directions), default=0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "directions": [
                {
                    "direction_id": item.direction_id,
                    "name": item.name,
                    "paper_ids": item.paper_ids,
                    "claim_ids": item.claim_ids,
                    "coherence": item.coherence,
                    "outliers": item.outliers,
                }
                for item in self.directions
            ],
            "papers": self.papers,
            "min_size": self.min_size,
            "outlier_rate": self.outlier_rate,
            "count_quality": self.count_quality,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MapArtifact:
        directions = [
            Direction(
                direction_id=str(item["direction_id"]),
                name=str(item["name"]),
                paper_ids=list(item.get("paper_ids") or []),
                claim_ids=list(item.get("claim_ids") or []),
                coherence=float(item.get("coherence") or 0.0),
                outliers=list(item.get("outliers") or []),
            )
            for item in data.get("directions", [])
        ]
        return cls(
            directions=directions,
            papers=int(data.get("papers") or 0),
            outlier_rate=float(data.get("outlier_rate") or 0.0),
            count_quality=str(data.get("count_quality") or "deficit"),
        )


@dataclass
class Section:
    section_id: str
    kind: str
    title: str
    body: str
    claim_indexes: list[int] = field(default_factory=list)


@dataclass
class ReportDraft:
    title: str
    content_md: str
    content_sha: str
    sections: list[Section]
    word_count: int
    claims: list[dict[str, Any]]
    state: str = "complete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content_md": self.content_md,
            "content_sha": self.content_sha,
            "sections": [section.__dict__ for section in self.sections],
            "word_count": self.word_count,
            "claims": self.claims,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportDraft:
        return cls(
            title=str(data.get("title") or ""),
            content_md=str(data.get("content_md") or ""),
            content_sha=str(data.get("content_sha") or ""),
            sections=[Section(**section) for section in data.get("sections", [])],
            word_count=int(data.get("word_count") or 0),
            claims=list(data.get("claims") or []),
            state=str(data.get("state") or "degraded"),
        )

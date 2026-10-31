"""Direction clustering for v2 S3."""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.domains.report.contracts import EvidenceArtifact

__all__ = ["Direction", "MapArtifact", "MapService"]


def artifact_min_size(directions: list[Direction]) -> int:
    return min((len(item.paper_ids) for item in directions), default=0)

_STOP = {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "with", "using",
    "we", "this", "that", "is", "are", "from", "by", "as", "our", "their",
}


def _grams(text: str) -> Counter[str]:
    words = [word for word in re.split(r"\W+", text.lower()) if len(word) > 3 and word not in _STOP]
    return Counter(words)


def _cos(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[k] * b[k] for k in common)
    den = math.sqrt(sum(v * v for v in a.values())) * math.sqrt(sum(v * v for v in b.values()))
    return num / den if den else 0.0


def _terms(text: str) -> list[str]:
    words = [w for w in re.split(r"\W+", text.lower()) if len(w) > 3 and w not in _STOP]
    return [word for word, _count in Counter(words).most_common(3)]


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


class MapService:
    def __init__(self, *, threshold: float = 0.35, min_size: int = 3, max_directions: int = 8) -> None:
        self.threshold = threshold
        self.min_size = min_size
        self.max_directions = max_directions

    def build(self, evidence: EvidenceArtifact) -> MapArtifact:
        by_paper = {item["paper_id"]: item for item in evidence.papers}
        ids = sorted(by_paper)
        vectors = {
            pid: _grams(
                " ".join(
                    [
                        str(by_paper[pid].get("title") or ""),
                        str(by_paper[pid].get("abstract") or ""),
                    ]
                    + [claim.get("text", "") for claim in by_paper[pid].get("claims", [])]
                    + [claim.get("quote", "") for claim in by_paper[pid].get("claims", [])]
                )
            )
            for pid in ids
        }
        groups: list[list[str]] = [[pid] for pid in ids]
        target = min(8, max(5, math.ceil(len(ids) / 15))) if ids else 0
        while len(groups) > target:
            best_pair: tuple[int, int] | None = None
            best_score = -1.0
            for left in range(len(groups)):
                for right in range(left + 1, len(groups)):
                    scores = [
                        _cos(vectors[a], vectors[b])
                        for a in groups[left]
                        for b in groups[right]
                    ]
                    score = sum(scores) / len(scores) if scores else 0.0
                    if score > best_score:
                        best_score = score
                        best_pair = (left, right)
            if best_pair is None:
                break
            left, right = best_pair
            groups[left] = sorted(groups[left] + groups[right])
            del groups[right]

        major: list[list[str]] = []
        small: list[str] = []
        for group in groups:
            (major if len(group) >= self.min_size else small).append(sorted(group))
        if small:
            major.append(sorted(item for group in small for item in group))
        major.sort(key=lambda group: (-len(group), group[0]))
        if len(major) > self.max_directions:
            keep = major[: self.max_directions - 1]
            keep.append(sorted(item for group in major[self.max_directions - 1 :] for item in group))
            major = keep

        directions: list[Direction] = []
        for index, group in enumerate(major, start=1):
            claims = [claim for pid in group for claim in by_paper[pid].get("claims", [])]
            text = " ".join(claim.get("text", "") for claim in claims)
            terms = _terms(text) or _terms(" ".join(by_paper[pid].get("paper_id", "") for pid in group))
            name = " / ".join(term.title() for term in terms[:2]) or f"Direction {index}"
            pair_scores = [
                _cos(vectors[a], vectors[b])
                for i, a in enumerate(group)
                for b in group[i + 1 :]
            ]
            directions.append(
                Direction(
                    direction_id=f"D{index}",
                    name=name,
                    paper_ids=group,
                    claim_ids=[str(claim["claim_id"]) for claim in claims],
                    coherence=round(sum(pair_scores) / len(pair_scores), 4) if pair_scores else 0.0,
                )
            )
        artifact = MapArtifact(
            directions=directions,
            papers=len(ids),
            outlier_rate=0.0,
            count_quality=(
                "complete"
                if 5 <= len(directions) <= 8 and artifact_min_size(directions) >= self.min_size
                else "deficit"
            ),
        )
        return artifact

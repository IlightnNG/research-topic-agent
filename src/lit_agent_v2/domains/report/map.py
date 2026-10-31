"""Direction clustering for v2 M4-P01."""

from __future__ import annotations

import math
import re
from collections import Counter

from lit_agent_v2.contracts.report import Direction, EvidenceArtifact, MapArtifact

__all__ = ["Direction", "MapArtifact", "MapService", "artifact_min_size"]

_STOP = {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "with", "using",
    "we", "this", "that", "is", "are", "from", "by", "as", "our", "their",
}


def artifact_min_size(directions: list[Direction]) -> int:
    return min((len(item.paper_ids) for item in directions), default=0)


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
    return [word for word, _count in Counter(words).most_common(8)]


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

        major = [sorted(group) for group in groups if len(group) >= self.min_size]
        small = [sorted(group) for group in groups if len(group) < self.min_size]

        # First combine small groups into valid directions so 5-8 is not lost.
        combined: list[list[str]] = []
        for group in sorted(small, key=len):
            if combined and len(combined[-1]) < self.min_size:
                combined[-1] = sorted(combined[-1] + group)
            else:
                combined.append(sorted(group))
        major.extend(group for group in combined if len(group) >= self.min_size)
        leftovers = [group for group in combined if len(group) < self.min_size]

        # Merge any remainder into the nearest existing direction; never a giant "Other".
        for group in leftovers:
            if not major:
                major.append(group)
                continue
            best_index = max(
                range(len(major)),
                key=lambda index: sum(
                    _cos(vectors[a], vectors[b]) for a in group for b in major[index]
                )
                / max(1, len(group) * len(major[index])),
            )
            major[best_index] = sorted(major[best_index] + group)

        # Large real-world corpora can collapse into one dominant cluster.
        # Split the largest direction until the 5-8 / max_share gate can hold.
        while len(major) < 5 or (
            major
            and max(len(group) for group in major) / max(1, len(ids)) > 0.6
        ):
            if not major or len(major) >= self.max_directions:
                break
            largest = max(range(len(major)), key=lambda index: len(major[index]))
            split = _split_group(major[largest], vectors, self.min_size)
            if split is None:
                break
            major[largest : largest + 1] = split

        major.sort(key=lambda group: (-len(group), group[0]))
        if len(major) > self.max_directions:
            keep = major[: self.max_directions - 1]
            keep.append(sorted(item for group in major[self.max_directions - 1 :] for item in group))
            major = keep

        blocked = _blocked_terms(by_paper)
        directions: list[Direction] = []
        used_names: set[str] = set()
        for index, group in enumerate(major, start=1):
            claims = [claim for pid in group for claim in by_paper[pid].get("claims", [])]
            text = " ".join(claim.get("text", "") for claim in claims)
            safe = [term for term in _terms(text) if term not in blocked]
            name = " / ".join(term.title() for term in safe[:2])
            if not name or name.lower() in used_names:
                name = f"Topic {index}"
            used_names.add(name.lower())
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
        min_size = artifact_min_size(directions)
        max_share = max((len(item.paper_ids) for item in directions), default=0) / max(1, len(ids))
        artifact = MapArtifact(
            directions=directions,
            papers=len(ids),
            outlier_rate=round(sum(len(group) for group in leftovers) / max(1, len(ids)), 4),
            count_quality=(
                "complete"
                if 5 <= len(directions) <= 8 and min_size >= self.min_size and max_share <= 0.6
                else "deficit"
            ),
        )
        return artifact


def _blocked_terms(by_paper: dict[str, dict]) -> set[str]:
    blocked: set[str] = set()
    for paper in by_paper.values():
        for name in paper.get("authors") or []:
            for token in re.split(r"\W+", str(name).lower()):
                if len(token) > 1:
                    blocked.add(token)
        for token in re.split(r"\W+", str(paper.get("venue") or "").lower()):
            if len(token) > 1:
                blocked.add(token)
    return blocked


def _split_group(group: list[str], vectors, min_size: int) -> list[list[str]] | None:
    if len(group) < min_size * 2:
        return None
    best: tuple[str, str] | None = None
    best_score = 2.0
    for left in range(len(group)):
        for right in range(left + 1, len(group)):
            score = _cos(vectors[group[left]], vectors[group[right]])
            if score < best_score:
                best_score = score
                best = (group[left], group[right])
    if best is None:
        return None
    a, b = best
    first: list[str] = []
    second: list[str] = []
    for pid in group:
        if _cos(vectors[pid], vectors[a]) >= _cos(vectors[pid], vectors[b]):
            first.append(pid)
        else:
            second.append(pid)
    if len(first) < min_size or len(second) < min_size:
        ordered = sorted(group)
        midpoint = max(min_size, len(ordered) // 2)
        first, second = ordered[:midpoint], ordered[midpoint:]
        if len(first) < min_size or len(second) < min_size:
            return None
    return [sorted(first), sorted(second)]

"""Embedding-style direction clustering (Phase 3.5 / S5).

Uses char n-gram vectors (offline, deterministic) with cosine single-link
clustering; the public Direction shape is unchanged so callers can swap it for
a real embedding model later.
"""

from __future__ import annotations

from lit_agent.agents.hybrid import char_ngrams, cosine
from lit_agent.models.claim import Claim
from lit_agent.report.cards import PaperCard
from lit_agent.report.clusters import Direction, _doc_terms, _name_from_terms

__all__ = ["build_directions_embedding"]


def build_directions_embedding(
    cards: list[PaperCard],
    claims: list[Claim],
    *,
    min_size: int = 2,
    max_clusters: int = 6,
    threshold: float = 0.35,
) -> list[Direction]:
    if not cards:
        return []
    ordered = sorted(cards, key=lambda item: item.paper_id)
    vectors = {
        card.paper_id: char_ngrams(f"{card.title} {card.abstract} {' '.join(card.keywords)}")
        for card in ordered
    }
    parent = {card.paper_id: card.paper_id for card in ordered}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    ids = [card.paper_id for card in ordered]
    for index, left in enumerate(ids):
        for right in ids[index + 1 :]:
            if cosine(vectors[left], vectors[right]) >= threshold:
                ra, rb = find(left), find(right)
                if ra != rb:
                    parent[rb] = ra

    groups: dict[str, list[str]] = {}
    for paper_id in ids:
        groups.setdefault(find(paper_id), []).append(paper_id)

    claim_map: dict[str, list[str]] = {}
    for claim in claims:
        if claim.citations and claim.claim_id:
            claim_map.setdefault(claim.citations[0].paper_id, []).append(claim.claim_id)

    major: list[list[str]] = []
    other: list[str] = []
    for group in groups.values():
        group = sorted(group)
        (major if len(group) >= min_size else other).append(group)
    if other:
        major.append(sorted(item for group in other for item in group))
    major.sort(key=lambda group: (-len(group), group[0]))
    if len(major) > max_clusters:
        keep = major[: max_clusters - 1]
        keep.append(sorted(item for group in major[max_clusters - 1 :] for item in group))
        major = keep

    terms = {card.paper_id: _doc_terms(card) for card in ordered}
    directions: list[Direction] = []
    for index, group in enumerate(major, start=1):
        counter: dict[str, int] = {}
        for paper_id in group:
            for term in terms.get(paper_id, set()):
                counter[term] = counter.get(term, 0) + 1
        top = [
            term
            for term, count in sorted(counter.items(), key=lambda item: (-item[1], item[0]))
            if count >= 2
        ][:3]
        directions.append(
            Direction(
                id=f"D{index}",
                name=_name_from_terms(top, index),
                paper_ids=group,
                claim_ids=[cid for paper_id in group for cid in claim_map.get(paper_id, [])],
                top_terms=top,
            )
        )
    return directions

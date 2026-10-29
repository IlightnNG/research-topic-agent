"""方向聚类（3.2 / S4）：轻量、确定性、无重依赖。

MVP 用词面 Jaccard 做单链接合并；后续可无缝替换为 embedding + HDBSCAN
（`cluster_cards` 的输入/输出不变）。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent.models.claim import Claim
from lit_agent.report.cards import PaperCard

__all__ = ["Direction", "build_directions", "label_directions"]

logger = logging.getLogger(__name__)

_STOP = {
    "the", "a", "an", "of", "for", "and", "to", "in", "on", "with", "using", "we", "this",
    # venue / publication boilerplate
    "acl", "emnlp", "naacl", "eacl", "coling", "neurips", "icml", "iclr", "aaai", "ijcai",
    "annual", "meeting", "association", "computational", "linguistics", "proceedings",
    "conference", "journal", "volume", "pages", "published", "paper", "papers", "authors",
    "et", "al", "https", "doi", "arxiv", "university", "institute",
}


def _terms(text: str) -> set[str]:
    words = {w for w in re.split(r"\W+", text.lower()) if len(w) > 2 and w not in _STOP}
    cjk = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    words |= {cjk[i : i + 2] for i in range(len(cjk) - 1)}
    return words


@dataclass
class Direction:
    id: str
    name: str
    paper_ids: list[str]
    claim_ids: list[str] = field(default_factory=list)
    top_terms: list[str] = field(default_factory=list)
    definition: str = ""
    origin: str = "algorithm"

    @property
    def size(self) -> int:
        return len(self.paper_ids)


def _doc_terms(card: PaperCard) -> set[str]:
    parts = [card.title, card.abstract, *card.keywords]
    parts.extend(str(item.get("text") or "") for item in card.claims)
    return _terms(" ".join(parts))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _name_from_terms(terms: list[str], index: int) -> str:
    if not terms:
        return f"Direction {index}"
    return " / ".join(term.title() for term in terms[:2])


def build_directions(
    cards: list[PaperCard],
    claims: list[Claim],
    *,
    min_size: int = 2,
    max_clusters: int = 6,
    threshold: float = 0.12,
) -> list[Direction]:
    """单链接 Jaccard 聚类；singletons 合并到 Other，保证确定性。"""
    if not cards:
        return []

    ordered = sorted(cards, key=lambda item: item.paper_id)
    terms = {card.paper_id: _doc_terms(card) for card in ordered}
    parent = {card.paper_id: card.paper_id for card in ordered}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    ids = [card.paper_id for card in ordered]
    for i, left in enumerate(ids):
        for right in ids[i + 1 :]:
            if _jaccard(terms[left], terms[right]) >= threshold:
                union(left, right)

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
        if len(group) >= min_size:
            major.append(group)
        else:
            other.extend(group)
    if other:
        major.append(sorted(other))

    # 超过 max_clusters：保留最大的，其余并入 Other
    major.sort(key=lambda group: (-len(group), group[0]))
    if len(major) > max_clusters:
        keep = major[: max_clusters - 1]
        merged: list[str] = []
        for group in major[max_clusters - 1 :]:
            merged.extend(group)
        keep.append(sorted(merged))
        major = keep

    directions: list[Direction] = []
    for index, group in enumerate(major, start=1):
        counter: dict[str, int] = {}
        for paper_id in group:
            for term in terms.get(paper_id, set()):
                counter[term] = counter.get(term, 0) + 1
        top = [term for term, count in sorted(counter.items(), key=lambda item: (-item[1], item[0])) if count >= 2][:3]
        claim_ids = [cid for paper_id in group for cid in claim_map.get(paper_id, [])]
        directions.append(
            Direction(
                id=f"D{index}",
                name=_name_from_terms(top, index),
                paper_ids=group,
                claim_ids=claim_ids,
                top_terms=top,
            )
        )

    logger.info(
        "report.clusters.built",
        extra={
            "papers": len(cards),
            "directions": len(directions),
            "other": len(other),
        },
    )
    return directions


def label_directions(
    directions: list[Direction],
    cards: list[PaperCard],
    *,
    gateway: Any | None = None,
    max_tokens: int = 240,
) -> list[Direction]:
    """可选 LLM 命名；失败/非法直接保留算法名。"""
    if gateway is None or not directions:
        return directions
    by_id = {card.paper_id: card for card in cards}
    for direction in directions:
        titles = [by_id[pid].title for pid in direction.paper_ids if pid in by_id]
        try:
            payload, _ = gateway.chat_json(
                [
                    {
                        "role": "system",
                        "content": (
                            "Name this research direction and define it in one sentence. "
                            'Return JSON: {"name": str, "definition": str}. '
                            "Use only the given paper titles; do not invent papers; "
                            "do not name venues or publication metadata."
                        ),
                    },
                    {"role": "user", "content": "\n".join(titles)},
                ],
                max_tokens=max_tokens,
                agent="report_clusters",
            )
            name = str(payload.get("name") or "").strip() if isinstance(payload, dict) else ""
            if name:
                direction.name = name[:80]
                direction.definition = str(payload.get("definition") or "")[:300]
        except Exception as exc:  # noqa: BLE001 - 命名失败不阻断
            logger.warning(
                "report.clusters.label_failed",
                extra={"direction": direction.id, "error": type(exc).__name__},
            )
    return directions

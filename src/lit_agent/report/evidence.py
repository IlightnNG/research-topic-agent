"""Tiered evidence selection (Phase 3.5 / S4).

L1: all cards; L2: deep-read subset; L3: claims with quote windows.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lit_agent.report.context import ReportContext

__all__ = ["EvidenceTiers", "select_evidence_tiers"]


@dataclass
class EvidenceTiers:
    l1_paper_ids: list[str] = field(default_factory=list)
    deep_paper_ids: list[str] = field(default_factory=list)
    quote_paper_ids: list[str] = field(default_factory=list)
    ratio: float = 0.0
    scores: dict[str, float] = field(default_factory=dict)

    def to_meta(self) -> dict[str, object]:
        return {
            "l1": len(self.l1_paper_ids),
            "deep": len(self.deep_paper_ids),
            "quote": len(self.quote_paper_ids),
            "ratio": self.ratio,
        }


def _score(context: ReportContext, paper_id: str) -> float:
    cards = {card.paper_id: card for card in context.cards}
    card = cards.get(paper_id)
    if card is None:
        return 0.0
    claims = context.claim_set.by_paper().get(paper_id, [])
    return round(len(claims) * 2.0 + min(len(card.abstract or ""), 1200) / 1200.0, 4)


def select_evidence_tiers(
    context: ReportContext,
    *,
    deep_ratio: float = 0.35,
    min_deep: int = 3,
    max_deep: int = 40,
) -> EvidenceTiers:
    ids = [card.paper_id for card in context.cards]
    scores = {paper_id: _score(context, paper_id) for paper_id in ids}
    ranked = sorted(ids, key=lambda paper_id: (-scores[paper_id], paper_id))
    ratio = min(1.0, max(0.0, deep_ratio))
    count = min(len(ids), max_deep, max(min_deep, math.ceil(len(ids) * ratio))) if ids else 0
    deep = ranked[:count]
    quote = [
        paper_id
        for paper_id in deep
        if any(claim.citations and claim.citations[0].paper_id == paper_id for claim in context.claim_set.claims)
    ]
    return EvidenceTiers(
        l1_paper_ids=ids,
        deep_paper_ids=deep,
        quote_paper_ids=quote,
        ratio=round(count / len(ids), 4) if ids else 0.0,
        scores=scores,
    )

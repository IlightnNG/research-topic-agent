"""证据检索 agent（S5）：按 focus_hint 与词面信号给候选打分。

S10 会把这里替换为 hybrid（关键词 + 向量 + rerank）；当前是**确定性基线**，
同时是"单一取数入口"：下游一律消费这里选出的 `paper_ids`。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent.models.evidence import EvidenceCard

__all__ = ["RetrievalResult", "run", "score_card", "select_cards", "tokens"]


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", text.lower()))


@dataclass
class RetrievalResult:
    cards: list[EvidenceCard] = field(default_factory=list)
    scored: dict[str, int] = field(default_factory=dict)
    dropped: int = 0

    @property
    def paper_ids(self) -> list[str]:
        return [card.paper_id for card in self.cards]


def score_card(card: EvidenceCard, hint_tokens: set[str]) -> int:
    """词面分：命中 hint token ×2 + 标题命中 ×1 + 有摘要 +1。"""
    haystack = f"{card.title} {card.snippet}"
    hits = len(hint_tokens & tokens(haystack))
    title_hits = len(hint_tokens & tokens(card.title))
    return hits * 2 + title_hits + (1 if card.snippet else 0)


def select_cards(
    cards: list[EvidenceCard],
    *,
    focus_hint: str | None = None,
    limit: int = 50,
) -> RetrievalResult:
    """无 hint 时按原序截断；有 hint 时只保留命中项（全不命中 → 空，显式降级）。"""
    hint_tokens = tokens(focus_hint or "")
    scored = {card.paper_id: score_card(card, hint_tokens) for card in cards}
    if hint_tokens:
        chosen = [
            card for card in cards if hint_tokens & tokens(f"{card.title} {card.snippet}")
        ]
    else:
        chosen = list(cards)
    chosen = sorted(chosen, key=lambda card: (-scored.get(card.paper_id, 0), card.paper_id))[:limit]
    return RetrievalResult(cards=chosen, scored=scored, dropped=len(cards) - len(chosen))


def run(state: dict[str, Any], **_: Any) -> dict[str, Any]:
    """LangGraph 兼容包装：读取上游 cards（或返回空）。"""
    cards = state.get("cards") or []
    result = select_cards(cards, focus_hint=state.get("focus_hint"))
    return {
        "artifacts": {"paper_ids": result.paper_ids, "selected": len(result.cards)},
        "counters": {"candidates": len(cards), "selected": len(result.cards)},
    }

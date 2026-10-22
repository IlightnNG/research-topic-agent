"""S10：char-ngram 向量 + 关键词的混合检索（可解释、零模型下载）。

为什么用 **char 3-gram** 而不是词向量：评测里要区分"词面命中"与"形态相近"，
char-ngram 能捕捉 `invoke / invocation / invoking` 这类形态变化，而词袋不能。
真实语义检索（bge-m3）留给 P3 的 rerank 升级，接口不变。
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Sequence
from typing import Any

from lit_agent.agents.retrieval import RetrievalResult, select_cards, tokens
from lit_agent.models.evidence import EvidenceCard

__all__ = ["char_ngrams", "cosine", "hybrid_search", "keyword_score", "rerank"]


def char_ngrams(text: str, size: int = 3) -> Counter[str]:
    clean = " ".join((text or "").lower().split())
    if len(clean) < size:
        return Counter({clean: 1}) if clean else Counter()
    return Counter(clean[index : index + size] for index in range(len(clean) - size + 1))


def cosine(left: Counter[str], right: Counter[str]) -> float:
    if not left or not right:
        return 0.0
    common = set(left) & set(right)
    numerator = sum(left[key] * right[key] for key in common)
    denom = math.sqrt(sum(v * v for v in left.values())) * math.sqrt(
        sum(v * v for v in right.values())
    )
    return numerator / denom if denom else 0.0


def keyword_score(card: EvidenceCard, query: str) -> float:
    query_tokens = tokens(query)
    if not query_tokens:
        return 0.0
    hits = len(query_tokens & tokens(f"{card.title} {card.snippet}"))
    return hits / len(query_tokens)


def rerank(
    cards: Sequence[EvidenceCard],
    query: str,
    *,
    alpha: float = 0.6,
) -> list[tuple[EvidenceCard, float]]:
    """`score = alpha * keyword + (1-alpha) * char-ngram cosine`。"""
    query_grams = char_ngrams(query)
    scored: list[tuple[EvidenceCard, float]] = []
    for card in cards:
        kw = keyword_score(card, query)
        vec = cosine(query_grams, char_ngrams(f"{card.title} {card.snippet}"))
        scored.append((card, round(alpha * kw + (1 - alpha) * vec, 6)))
    return sorted(scored, key=lambda item: (-item[1], item[0].paper_id))


def hybrid_search(
    cards: Sequence[EvidenceCard],
    query: str,
    *,
    k: int = 10,
    alpha: float = 0.6,
    min_score: float = 0.15,
    min_relative: float = 0.5,
) -> RetrievalResult:
    """混合检索：返回相关 top-k。

    两道阈值（否则"top-k 全返回"会丢掉聚焦语义）：
    - 绝对：`score >= min_score`；
    - 相对：`score >= top_score * min_relative`（去掉明显陪跑项）。
    """
    ranked = rerank(cards, query, alpha=alpha)
    if not ranked:
        return RetrievalResult(cards=[], scored={}, dropped=0)
    top = ranked[0][1]
    floor = max(min_score, top * min_relative)
    kept = [(card, score) for card, score in ranked if score >= floor][:k]
    return RetrievalResult(
        cards=[card for card, _score in kept],
        scored={card.paper_id: score for card, score in kept},  # type: ignore[dict-item]
        dropped=max(0, len(cards) - len(kept)),
    )


def keyword_only(cards: Sequence[EvidenceCard], query: str, *, k: int = 10) -> list[EvidenceCard]:
    """基线：纯词面（评测对照用）。"""
    scored = sorted(
        ((card, keyword_score(card, query)) for card in cards),
        key=lambda item: (-item[1], item[0].paper_id),
    )
    return [card for card, score in scored[:k] if score > 0]


def run(state: dict[str, Any], *, cards: list[EvidenceCard] | None = None, **_: Any) -> dict[str, Any]:
    """LangGraph 包装（S10 接线用）。"""
    query = str(state.get("focus_hint") or (state.get("artifacts") or {}).get("query") or "")
    result = hybrid_search(cards or [], query) if query else select_cards(cards or [])
    return {
        "artifacts": {"paper_ids": result.paper_ids, "selected": len(result.cards)},
        "counters": {"selected": len(result.cards)},
    }

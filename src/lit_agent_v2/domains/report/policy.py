"""Report sizing policy derived from corpus size, not hard-coded."""

from __future__ import annotations

import math
from dataclasses import dataclass

__all__ = ["ReportPolicy", "policy_for"]


@dataclass(frozen=True)
class ReportPolicy:
    papers: int
    target_directions: int
    min_directions: int
    max_directions: int
    min_direction_size: int
    max_direction_share: float
    target_words: int
    min_words: int
    max_words: int


def policy_for(papers: int, claims: int = 0) -> ReportPolicy:
    n = max(1, papers)
    target = min(12, max(3, math.ceil(n / 20) + 2))
    min_directions = max(3, target - 2)
    max_directions = min(12, target + 2)
    min_size = max(3, math.floor(n / (2 * target)))
    max_share = min(0.6, max(0.3, 2.5 / target))
    target_words = min(8000, max(1200, 600 + 20 * n + 10 * claims))
    return ReportPolicy(
        papers=n,
        target_directions=target,
        min_directions=min_directions,
        max_directions=max_directions,
        min_direction_size=min_size,
        max_direction_share=max_share,
        target_words=target_words,
        min_words=round(target_words * 0.4),
        max_words=round(target_words * 1.6),
    )

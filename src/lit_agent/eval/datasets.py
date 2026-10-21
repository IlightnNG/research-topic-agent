"""Gold 小集（S6）：20 条 claim/snippet/标签，用于校准 grounding 判定器。

**冻结**：改动条目必须重跑全量评测并在 ADR 记录（禁止为通过实现而改 gold）。
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["GOLD", "GoldItem", "load_gold"]


@dataclass(frozen=True)
class GoldItem:
    claim: str
    snippet: str
    label: str  # supported | unsupported


def _supported(topic: str, detail: str) -> GoldItem:
    return GoldItem(
        claim=f"{topic} improves {detail} in agent systems",
        snippet=f"We show that {topic} improves {detail} across agent systems benchmarks.",
        label="supported",
    )


def _unsupported(topic: str) -> GoldItem:
    return GoldItem(
        claim=f"{topic} guarantees deterministic planning under budget",
        snippet="The paper studies protein folding kinetics with cryo electron microscopy.",
        label="unsupported",
    )


_TOPICS = [
    ("tool use", "task success"),
    ("retrieval augmentation", "answer faithfulness"),
    ("multi agent debate", "reasoning accuracy"),
    ("memory modules", "long horizon coherence"),
    ("planner critic loops", "error recovery"),
    ("context compression", "cost efficiency"),
    ("citation grounding", "hallucination reduction"),
    ("graph mapping", "author disambiguation"),
    ("weekly reporting", "coverage of new work"),
    ("focus hints", "retrieval precision"),
]

#: 10 条正例 + 10 条负例 = 20（冻结）
GOLD: tuple[GoldItem, ...] = tuple(
    [_supported(topic, detail) for topic, detail in _TOPICS]
    + [_unsupported(topic) for topic, _detail in _TOPICS]
)


def load_gold() -> list[GoldItem]:
    return list(GOLD)

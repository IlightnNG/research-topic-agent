"""ReportContext（3.2 / S3–S4）：PaperCard → Claims → Directions 的可复用装配。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from lit_agent.config import Settings
from lit_agent.report.cards import PaperCard, get_or_build_card
from lit_agent.report.claims import ClaimSet, build_claims
from lit_agent.report.clusters import Direction, build_directions, label_directions

__all__ = ["ReportContext", "build_context"]

logger = logging.getLogger(__name__)


@dataclass
class ReportContext:
    cards: list[PaperCard] = field(default_factory=list)
    claim_set: ClaimSet = field(default_factory=ClaimSet)
    directions: list[Direction] = field(default_factory=list)
    meta: dict[str, object] = field(default_factory=dict)


def build_context(
    settings: Settings,
    paper_ids: list[str],
    *,
    gateway: object | None = None,
) -> ReportContext:
    """按 paper_id 构建卡片（缓存）、claims、方向；失败只影响单篇。"""
    cards: list[PaperCard] = []
    failed: list[str] = []
    for paper_id in sorted(set(paper_ids)):
        try:
            cards.append(get_or_build_card(settings, paper_id, gateway=gateway, write_cache=False))
        except Exception as exc:  # noqa: BLE001 - 单篇失败不阻断报告
            failed.append(paper_id)
            logger.warning(
                "report.context.card_failed",
                extra={"paper_id": paper_id, "error": type(exc).__name__},
            )

    claim_set = build_claims(cards, max_per_paper=settings.report.max_claims_per_paper)
    directions = build_directions(
        cards,
        claim_set.claims,
        min_size=settings.report.min_cluster_size,
        max_clusters=settings.report.max_sections,
        threshold=settings.report.cluster_threshold,
    )
    directions = label_directions(directions, cards, gateway=gateway)

    logger.info(
        "report.context.built",
        extra={
            "papers": len(cards),
            "failed": len(failed),
            "claims": len(claim_set.claims),
            "directions": len(directions),
        },
    )
    return ReportContext(
        cards=cards,
        claim_set=claim_set,
        directions=directions,
        meta={
            "papers": len(cards),
            "failed_papers": failed,
            "duplicates": claim_set.duplicates,
            "dropped_claims": claim_set.dropped,
        },
    )

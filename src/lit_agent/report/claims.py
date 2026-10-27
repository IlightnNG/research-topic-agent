"""Claim 规范化（3.2 / S3）：稳定 ID、跨论文去重、每篇上限。"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, Support
from lit_agent.report.cards import PaperCard

__all__ = ["ClaimSet", "build_claims"]

logger = logging.getLogger(__name__)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _sha(text: str) -> str:
    return hashlib.sha256(_norm(text).encode("utf-8")).hexdigest()


@dataclass
class ClaimSet:
    claims: list[Claim] = field(default_factory=list)
    duplicates: int = 0
    dropped: int = 0

    def by_paper(self) -> dict[str, list[Claim]]:
        out: dict[str, list[Claim]] = {}
        for claim in self.claims:
            if claim.citations:
                out.setdefault(claim.citations[0].paper_id, []).append(claim)
        return out


def build_claims(cards: list[PaperCard], *, max_per_paper: int = 3) -> ClaimSet:
    """按 paper_id 排序分配 `P12-C1`；跨论文按 text_sha 去重。"""
    result = ClaimSet()
    seen: set[str] = set()

    for card in sorted(cards, key=lambda item: item.paper_id):
        kept = 0
        for item in card.claims:
            if kept >= max_per_paper:
                break
            text = str(item.get("text") or "").strip()
            quote = str(item.get("quote") or "").strip()
            if not text or not quote:
                result.dropped += 1
                continue
            digest = _sha(text)
            if digest in seen:
                result.duplicates += 1
                continue
            seen.add(digest)
            kept += 1
            result.claims.append(
                Claim(
                    text=text[:500],
                    citations=[Citation(paper_id=card.paper_id, snippet=quote[:500])],
                    support=Support.SUPPORTED,
                    claim_id=f"{card.paper_id}-C{kept}",
                    text_sha=digest,
                )
            )

    logger.info(
        "report.claims.built",
        extra={
            "claims": len(result.claims),
            "duplicates": result.duplicates,
            "dropped": result.dropped,
        },
    )
    return result

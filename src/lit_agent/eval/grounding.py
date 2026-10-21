"""Grounding 判定器（S6）：claim ↔ 证据片段是否真的被支持。

**可判定实现**（词面覆盖 + 引用存在性），不依赖 LLM：
- 词面：claim 的有效 token 中至少 `MIN_COVERAGE` 能在片段里找到；
- 引用：claim 必须至少有一条 citation；
- 两者都满足才算 `supported`。

S11 会用 gold 集校准阈值（阈值改动必须重跑全量，写进 ADR）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent.models.claim import Claim

__all__ = ["GroundingResult", "MIN_COVERAGE", "check_claim", "grounding_metrics", "tokens"]

MIN_COVERAGE = 0.5
MIN_TOKENS = 3


def tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]{3,}", (text or "").lower()))


@dataclass
class GroundingResult:
    supported: bool
    coverage: float
    has_citation: bool
    matched: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        return round(self.coverage * (1.0 if self.has_citation else 0.5), 4)


def check_claim(claim: Claim, snippets: list[str] | None = None) -> GroundingResult:
    """判定单条 claim 是否被其引用片段支持。"""
    material = " ".join(
        [*(snippets or []), *[citation.snippet or "" for citation in claim.citations]]
    )
    claim_tokens = tokens(claim.text)
    material_tokens = tokens(material)
    if len(claim_tokens) < MIN_TOKENS:
        coverage = 0.0
    else:
        coverage = len(claim_tokens & material_tokens) / len(claim_tokens)
    return GroundingResult(
        supported=bool(claim.citations) and coverage >= MIN_COVERAGE,
        coverage=round(coverage, 4),
        has_citation=bool(claim.citations),
        matched=sorted(claim_tokens & material_tokens)[:10],
    )


def grounding_metrics(claims: list[Claim]) -> dict[str, Any]:
    results = [check_claim(claim) for claim in claims]
    total = len(results)
    supported = sum(1 for result in results if result.supported)
    return {
        "total": total,
        "supported": supported,
        "unsupported": total - supported,
        "grounding_rate": (supported / total) if total else None,
        "mean_coverage": round(sum(r.coverage for r in results) / total, 4) if total else None,
    }

"""Claim extraction adapters for v2."""

from __future__ import annotations

import re
from typing import Any, Protocol

from lit_agent_v2.contracts.report import Claim

__all__ = ["LLMClaimExtractor", "extract_deterministic"]


_NON_RESEARCH = re.compile(
    r"(published at|proceedings of|we thank|et al\.|copyright|accepted to|acl 20|emnlp 20)",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 20]


def extract_deterministic(paper_id: str, text: str, limit: int = 2) -> list[Claim]:
    claims: list[Claim] = []
    for sentence in _sentences(text)[:limit]:
        if _NON_RESEARCH.search(sentence):
            continue
        claims.append(
            Claim(
                claim_id=f"{paper_id}-C{len(claims) + 1}",
                paper_id=paper_id,
                text=sentence[:400],
                quote=sentence,
            )
        )
    return claims


class LLMClient(Protocol):
    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> tuple[dict, Any]: ...


class LLMClaimExtractor:
    def __init__(self, client: LLMClient, *, max_claims: int = 2) -> None:
        self.client = client
        self.max_claims = max_claims

    def __call__(self, paper_id: str, text: str) -> list[Claim]:
        payload, _ = self.client.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract research claims. Every claim MUST copy an exact verbatim "
                        'quote from the text. Return JSON only: {"claims":[{"text":str,'
                        '"quote":str}]}. Reject bibliographic/authorship claims.'
                    ),
                },
                {"role": "user", "content": text[:6000]},
            ],
            max_tokens=500,
        )
        claims: list[Claim] = []
        for item in (payload.get("claims") or [])[: self.max_claims]:
            quote = str(item.get("quote") or "").strip()
            claim_text = str(item.get("text") or "").strip()
            if not quote or quote not in text or not claim_text:
                continue
            claims.append(
                Claim(
                    claim_id=f"{paper_id}-C{len(claims) + 1}",
                    paper_id=paper_id,
                    text=claim_text[:400],
                    quote=quote,
                    confidence=0.7,
                )
            )
        return claims

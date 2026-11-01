"""Claim extraction with type classification and non-research rejection."""

from __future__ import annotations

import re
from typing import Any, Protocol

from lit_agent_v2.contracts.report import Claim

__all__ = [
    "LLMClaimExtractor",
    "build_claim",
    "classify_claim",
    "extract_deterministic",
    "is_research_claim",
]


_AUTHOR_NAME = re.compile(r"\b[A-Z][a-z]+(?:\s+[A-Z]\.)?\s+[A-Z][a-z]+\b")
_REFERENCE = re.compile(
    r"(arxiv:|doi:|https?://|in proceedings|proceedings of|pp\.|et al\.|vol\.|no\.)",
    re.IGNORECASE,
)
_ACK = re.compile(r"(we thank|funded by|grant no|acknowledg)", re.IGNORECASE)
_COPYRIGHT = re.compile(r"(copyright|©|all rights reserved)", re.IGNORECASE)
_BACKGROUND = re.compile(
    r"^(large language models|recently|recent |with the|the rapid|advances in|in recent years)",
    re.IGNORECASE,
)
_CLAIM_VERB = re.compile(
    r"\b(show|shows|find|finds|demonstrat|propos|introduc|improv|achiev|reduc|increas|"
    r"outperform|enabl|suggest|reveal|report|observ|indicat|provid|leverag|present|fail|struggle|use|uses|using|"
    r"compare|evaluate|measure|support)\w*",
    re.IGNORECASE,
)
_TRUNCATED_END = re.compile(r"\b(as|the|of|and|with|by|algorit|for|to|in)$", re.IGNORECASE)
_LIMITATION = re.compile(r"\b(limitation|fail|struggle|however|challenge|not robust)\b", re.IGNORECASE)
_DATASET = re.compile(r"\b(dataset|benchmark|corpus|test set)\b", re.IGNORECASE)
_METHOD = re.compile(r"\b(we propose|we introduce|framework|method|approach|architecture)\b", re.IGNORECASE)


def _norm(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _sentences(text: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if len(part.strip()) >= 20]


def _author_list(sentence: str) -> bool:
    names = _AUTHOR_NAME.findall(sentence)
    if len(names) >= 2 and ("," in sentence or " and " in sentence):
        return not _CLAIM_VERB.search(sentence)
    return False


def _truncated(sentence: str) -> bool:
    text = sentence.strip()
    if text and text[-1] not in ".!?":
        return True
    if _TRUNCATED_END.search(text.rstrip(".!?")):
        return True
    return text.count("(") != text.count(")") or text.count('"') % 2 == 1


def classify_claim(sentence: str) -> str:
    if _LIMITATION.search(sentence):
        return "limitation"
    if _METHOD.search(sentence):
        return "method"
    if _DATASET.search(sentence) and not re.search(r"\bimprov|outperform|achiev", sentence, re.I):
        return "dataset"
    if _BACKGROUND.search(sentence) and not _CLAIM_VERB.search(sentence):
        return "background"
    return "finding"


def is_research_claim(sentence: str) -> bool:
    return classify_claim(sentence) != "background"


def build_claim(
    paper_id: str,
    sentence: str,
    *,
    source: str,
    claim_type: str | None = None,
    claim_id: str = "",
) -> Claim | None:
    text = _norm(sentence)
    quote = _norm(sentence)
    if not text or not source or quote not in _norm(source):
        return None
    if len(text.split()) < 8 or len(text) > 400:
        return None
    if _author_list(text) or _REFERENCE.search(text) or _ACK.search(text) or _COPYRIGHT.search(text):
        return None
    if _truncated(text):
        return None
    if not _CLAIM_VERB.search(text):
        return None
    kind = (
        claim_type
        if claim_type in {"finding", "method", "dataset", "limitation", "background"}
        else classify_claim(text)
    )
    if kind == "background":
        return None
    return Claim(
        claim_id=claim_id,
        paper_id=paper_id,
        text=text,
        quote=quote,
        claim_type=kind,
        confidence=0.7,
    )


def extract_deterministic(paper_id: str, text: str, limit: int = 2) -> list[Claim]:
    claims: list[Claim] = []
    for sentence in _sentences(text):
        claim = build_claim(
            paper_id,
            sentence,
            source=text,
            claim_id=f"{paper_id}-C{len(claims) + 1}",
        )
        if claim is None:
            continue
        claims.append(claim)
        if len(claims) >= limit:
            break
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
                        "Extract research claims. Every claim MUST have an exact verbatim quote. "
                        "Reject author lists, affiliations, references, acknowledgements, copyright. "
                        "Classify each claim: finding|method|dataset|limitation|background. "
                        'Return JSON only: {"claims":[{"text":str,"quote":str,"type":str}]}'
                    ),
                },
                {"role": "user", "content": text[:6000]},
            ],
            max_tokens=600,
        )
        claims: list[Claim] = []
        for item in (payload.get("claims") or [])[: self.max_claims]:
            if not isinstance(item, dict):
                continue
            claim = build_claim(
                paper_id,
                str(item.get("quote") or ""),
                source=text,
                claim_type=str(item.get("type") or ""),
                claim_id=f"{paper_id}-C{len(claims) + 1}",
            )
            if claim is not None:
                claims.append(claim)
        return claims

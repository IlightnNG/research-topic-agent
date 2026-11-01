"""Claim and quote tools."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.research.claims import extract_deterministic

__all__ = ["build_claim_tools", "check_quote", "extract_claims"]


def extract_claims(paper_id: str, text: str, limit: int = 2) -> dict[str, Any]:
    claims = extract_deterministic(paper_id, text, limit=limit)
    return {"claims": [claim.to_dict() for claim in claims], "count": len(claims)}


def check_quote(quote: str, text: str) -> dict[str, Any]:
    normalized_quote = " ".join(quote.split())
    normalized_text = " ".join(text.split())
    return {"ok": bool(normalized_quote) and normalized_quote in normalized_text}


def build_claim_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            "claims.extract",
            "Extract up to N exact-quote research claims from paper text.",
            {
                "type": "object",
                "properties": {
                    "paper_id": {"type": "string"},
                    "text": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["paper_id", "text"],
            },
            {"type": "object"},
            handler=lambda args: extract_claims(
                args["paper_id"], args["text"], int(args.get("limit", 2))
            ),
        ),
        ToolSpec(
            "quote.check",
            "Check that a quote appears in source text after whitespace normalization.",
            {
                "type": "object",
                "properties": {"quote": {"type": "string"}, "text": {"type": "string"}},
                "required": ["quote", "text"],
            },
            {"type": "object"},
            handler=lambda args: check_quote(args["quote"], args["text"]),
        ),
    ]

"""Rule evaluators and judge interface (S18)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent.report.claims import is_research_claim

__all__ = ["Evaluation", "LLMJudge", "RuleEvaluator"]


@dataclass
class Evaluation:
    metrics: dict[str, float] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


class RuleEvaluator:
    def claims(self, claims: list[dict[str, Any]]) -> Evaluation:
        if not claims:
            return Evaluation({"claim.purity": 0.0, "claim.citation_coverage": 0.0}, ["no claims"])
        pure = sum(1 for claim in claims if is_research_claim(str(claim.get("text") or "")))
        cited = sum(1 for claim in claims if claim.get("citations"))
        return Evaluation(
            {
                "claim.purity": round(pure / len(claims), 4),
                "claim.citation_coverage": round(cited / len(claims), 4),
            }
        )

    def sections(self, sections: list[dict[str, Any]]) -> Evaluation:
        deep = [item for item in sections if item.get("kind") == "deep_dive"]
        if not deep:
            return Evaluation({"report.sections": float(len(sections))}, ["no deep dives"])
        missing = [str(item.get("id")) for item in deep if not item.get("claim_indexes")]
        return Evaluation(
            {"report.sections": float(len(sections))},
            [f"{item}: no claims" for item in missing],
        )


class Judge(Protocol):
    def score(self, artifact: Any, rubric: str) -> dict[str, float]: ...


class LLMJudge:
    """Fixed-prompt judge; outputs dimensions, never used as a hard gate alone."""

    def __init__(self, gateway: Any, *, model: str | None = None) -> None:
        self.gateway = gateway
        self.model = model

    def score(self, artifact: Any, rubric: str) -> dict[str, float]:
        payload, _ = self.gateway.chat_json(
            [
                {
                    "role": "system",
                    "content": (
                        "Score the artifact using the rubric. Return JSON only with "
                        '{"relevance":1-5,"readability":1-5,"trust":1-5,"actionability":1-5}.'
                    ),
                },
                {"role": "user", "content": f"RUBRIC:\n{rubric}\n\nARTIFACT:\n{artifact!r}"},
            ],
            max_tokens=200,
            agent="judge",
        )
        if not isinstance(payload, dict):
            return {}
        return {
            key: float(payload.get(key) or 0)
            for key in ("relevance", "readability", "trust", "actionability")
        }


RUBRIC = """\
1 = unusable; 3 = acceptable; 5 = excellent.
Relevance: on-topic and specific.
Readability: structured, concise, no boilerplate.
Trust: every factual claim has a citation.
Actionability: tells a researcher what to read or try next.
"""

_ = json  # keep json import available for future structured judges

"""M5-P01: LLM judge with a fixed rubric."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

from lit_agent_v2.metrics.scorecard import JudgeScores

__all__ = ["JudgeError", "JudgePort", "JudgeResult", "LLMJudge", "RUBRIC"]

RUBRIC: dict[str, str] = {
    "relevance": "1 off-topic, 3 partly relevant, 5 precisely on-topic",
    "coverage": "1 major omissions, 3 mostly covered, 5 comprehensive",
    "grounding": "1 unsupported, 3 partly cited, 5 every claim traceable",
    "synthesis": "1 list-like, 3 some comparison, 5 genuine insight",
    "readability": "1 hard to read, 3 readable, 5 clear",
    "actionability": "1 useless, 3 generic, 5 concrete next steps",
}


class JudgeError(RuntimeError):
    pass


class JudgePort(Protocol):
    def score(self, text: str, claims: list[dict[str, Any]]) -> JudgeResult: ...


@dataclass
class JudgeResult:
    scores: JudgeScores
    problems: list[str] = field(default_factory=list)
    verdict: str = "repair"


class LLMJudge:
    def __init__(self, client) -> None:
        self.client = client

    def score(self, text: str, claims: list[dict[str, Any]]) -> JudgeResult:
        claim_refs = [
            {
                "ref": f"C{index + 1}",
                "paper_id": claim.get("paper_id"),
                "text": claim.get("text"),
            }
            for index, claim in enumerate(claims)
        ]
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are an independent research report judge. Score only the supplied "
                    "report against the supplied claims. Do not infer the producer's reasoning. "
                    "Use 1-5 integers. Return JSON only: "
                    '{"scores":{"relevance":1-5,"coverage":1-5,"grounding":1-5,'
                    '"synthesis":1-5,"readability":1-5,"actionability":1-5},'
                    '"problems":[str],"verdict":"accept|repair|fail"}. '
                    "Rubric: " + json.dumps(RUBRIC, ensure_ascii=False)
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"report": text[:12000], "claims": claim_refs}, ensure_ascii=False
                ),
            },
        ]
        payload, _usage = self.client.chat_json(prompt, max_tokens=1200)
        raw = payload.get("scores") or {}
        values: dict[str, float] = {}
        for key in RUBRIC:
            try:
                value = float(raw[key])
            except (KeyError, TypeError, ValueError) as exc:
                raise JudgeError(f"missing/invalid judge score: {key}") from exc
            if not 1 <= value <= 5:
                raise JudgeError(f"judge score out of range: {key}={value}")
            values[key] = value
        verdict = str(payload.get("verdict") or "repair")
        if verdict not in {"accept", "repair", "fail"}:
            verdict = "repair"
        return JudgeResult(
            scores=JudgeScores(**values),
            problems=[str(item) for item in payload.get("problems") or []],
            verdict=verdict,
        )

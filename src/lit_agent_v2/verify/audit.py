"""LLM audit verifier.

The audit sees the candidate output and declared inputs, never the producer's
chain-of-thought or tool trace.
"""

from __future__ import annotations

import json
from typing import Any

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.contracts.verdict import AuditResult
from lit_agent_v2.verify.ports import AuditLLMPort

__all__ = ["AuditVerifier"]


class AuditVerifier:
    def __init__(self, llm: AuditLLMPort, *, min_score: float = 3.5) -> None:
        self.llm = llm
        self.min_score = min_score

    def audit(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> AuditResult:
        prompt = (
            "Audit one Node output. Do not rewrite it. Do not infer missing facts.\n"
            "Score each dimension 1-5: relevance, coverage, readability, grounding.\n"
            "Return JSON only:\n"
            '{"verdict":"accept|repair","scores":{"relevance":5,"coverage":5,'
            '"readability":5,"grounding":5},"problems":[]}\n'
            f"Node: {node.id}\nGoal: {node.goal}\n"
            f"Inputs: {json.dumps(context.inputs, ensure_ascii=False, default=str)[:4000]}\n"
            f"Output: {json.dumps(result.output, ensure_ascii=False, default=str)[:8000]}"
        )
        messages = [
            {"role": "system", "content": "You are a strict but concise output auditor."},
            {"role": "user", "content": prompt},
        ]
        try:
            payload, _usage = self.llm.chat_json(
                messages,
                prompt_version=f"audit-{node.id}-v1",
                max_tokens=1200,
                temperature=0.0,
            )
        except Exception as exc:  # noqa: BLE001
            return AuditResult(accepted=False, verdict="repair", problems=[f"audit_error:{type(exc).__name__}"])
        return self._parse(payload)

    def _parse(self, payload: Any) -> AuditResult:
        if not isinstance(payload, dict):
            return AuditResult(accepted=False, verdict="repair", problems=["audit_non_object"])
        raw_scores = payload.get("scores")
        scores: dict[str, float] = {}
        if isinstance(raw_scores, dict):
            for key, value in raw_scores.items():
                if isinstance(value, (int, float)):
                    scores[str(key)] = float(value)
        problems = payload.get("problems")
        if not isinstance(problems, list):
            problems = []
        verdict = str(payload.get("verdict") or "repair")
        accepted = (
            verdict == "accept"
            and not problems
            and all(score >= self.min_score for score in scores.values())
        )
        if not scores and verdict == "accept" and not problems:
            accepted = True
        return AuditResult(
            scores=scores,
            problems=[str(problem) for problem in problems],
            verdict=verdict,
            accepted=accepted,
        )

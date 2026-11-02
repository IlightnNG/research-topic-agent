"""Optional LLM quality audit for the generic AgentKernel."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

__all__ = ["AuditReport", "LLMAuditor"]


@dataclass
class AuditReport:
    accepted: bool
    scores: dict[str, float] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


class LLMAuditor:
    def __init__(self, llm: Any, *, min_score: float = 3.0) -> None:
        self.llm = llm
        self.min_score = min_score

    def audit(
        self,
        goal: str,
        output: dict[str, Any],
        *,
        trace: list[dict[str, Any]] | None = None,
    ) -> AuditReport:
        trace_text = ""
        if trace:
            trace_text = "\nExecution trace:\n" + json.dumps(
                [
                    {
                        "role": item.get("role"),
                        "tool": item.get("name"),
                        "ok": item.get("ok"),
                        "content": str(item.get("content") or "")[:500],
                    }
                    for item in trace[-20:]
                ],
                ensure_ascii=False,
                default=str,
            )[:5000]
        prompt = (
            "Audit one task output and its execution trace. Do not rewrite it. "
            "Score 1-5 on relevance, grounding, completeness and clarity. "
            "For grounding, use the tool results in the trace. Return JSON only: "
            '{"verdict":"accept|repair","scores":{"relevance":5,'
            '"grounding":5,"completeness":5,"clarity":5},"problems":[]}\n'
            f"Goal: {goal}\n"
            f"Output: {json.dumps(output, ensure_ascii=False, default=str)[:5000]}"
            f"{trace_text}"
        )
        last_error: Exception | None = None
        for _attempt in range(2):
            try:
                payload, _ = self.llm.chat_json(
                    [
                        {"role": "system", "content": "You are a strict output auditor."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=700,
                    temperature=0.0,
                )
                break
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                payload = None
        if payload is None:
            return AuditReport(False, problems=[f"audit_error:{type(last_error).__name__}"])
        if not isinstance(payload, dict):
            return AuditReport(False, problems=["audit_non_object"])
        scores = payload.get("scores") or {}
        numeric = {
            str(key): float(value)
            for key, value in scores.items()
            if isinstance(value, (int, float))
        }
        problems = [str(item) for item in (payload.get("problems") or [])]
        accepted = (
            payload.get("verdict") == "accept"
            and not problems
            and all(score >= self.min_score for score in numeric.values())
        )
        return AuditReport(accepted=accepted, scores=numeric, problems=problems)

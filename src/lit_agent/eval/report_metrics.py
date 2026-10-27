"""报告质量指标（3.2 / S7）：只读 reports / claims，可复算。"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine

__all__ = ["run_report_metrics"]


def _ratio(numerator: float, denominator: float) -> float | None:
    return None if denominator <= 0 else round(numerator / denominator, 4)


def run_report_metrics(settings: Settings, run_id: str) -> dict[str, Any]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT content_md, word_count, sections_json, claims_json,"
                    " generated_by, fallback_reason, degraded"
                    " FROM reports WHERE run_id = :rid ORDER BY created_at DESC LIMIT 1"
                ),
                {"rid": run_id},
            ).first()
    finally:
        engine.dispose()

    if row is None:
        return {
            "report_words": None,
            "report_sections": None,
            "report_claims": None,
            "report_cited_claims": None,
            "report_cited_ratio": None,
            "report_fallback": None,
            "report_generated_llm": None,
        }

    content, words, sections_json, claims_json, generated_by, fallback, degraded = row
    sections = json.loads(sections_json or "[]")
    claims = json.loads(claims_json or "[]")
    cited = sum(1 for claim in claims if claim.get("citations"))
    return {
        "report_words": int(words or len(str(content or "").split())),
        "report_sections": len(sections) if isinstance(sections, list) else 0,
        "report_claims": len(claims) if isinstance(claims, list) else 0,
        "report_cited_claims": cited,
        "report_cited_ratio": _ratio(cited, len(claims) if isinstance(claims, list) else 0),
        "report_fallback": 1 if fallback or degraded else 0,
        "report_generated_llm": 1 if generated_by == "llm" else 0,
    }

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
                    " generated_by, fallback_reason, degraded, fallback_count, coverage, thin"
                    " FROM reports WHERE run_id = :rid ORDER BY created_at DESC LIMIT 1"
                ),
                {"rid": run_id},
            ).first()
            calls = conn.execute(
                text(
                    "SELECT COUNT(*), COALESCE(SUM(cache_hit), 0),"
                    " COALESCE(SUM(CASE WHEN ok = 0 THEN 1 ELSE 0 END), 0)"
                    " FROM llm_calls WHERE run_id = :rid"
                ),
                {"rid": run_id},
            ).one()
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
            "report_fallback_count": None,
            "report_coverage": None,
            "report_thin": None,
            "report_llm_calls": None,
            "report_cache_hits": None,
            "report_cache_hit_rate": None,
            "report_llm_failures": None,
        }

    (
        content,
        words,
        sections_json,
        claims_json,
        generated_by,
        fallback,
        degraded,
        fallback_count,
        coverage,
        thin,
    ) = row
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
        "report_generated_llm": 1 if generated_by in {"llm", "hybrid"} else 0,
        "report_fallback_count": int(fallback_count or 0),
        "report_coverage": float(coverage or 0.0),
        "report_thin": 1 if thin else 0,
        "report_llm_calls": int(calls[0] or 0),
        "report_cache_hits": int(calls[1] or 0),
        "report_cache_hit_rate": _ratio(float(calls[1] or 0), float(calls[0] or 0)),
        "report_llm_failures": int(calls[2] or 0),
    }

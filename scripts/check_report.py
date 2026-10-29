"""Smoke-check a generated report: structure, claims, citations, and size.

Usage:
    . .\scripts\env.ps1
    uv run python scripts/check_report.py --topic ai-agents --language en
    uv run python scripts/check_report.py --topic ai-agents --language zh --no-llm

Exit code 0 = structurally valid (a `thin` warning is still 0).
Exit code 1 = missing report / no claims / broken citations.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqlalchemy import text  # noqa: E402

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.db.session import connect, make_engine  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate and inspect one report")
    parser.add_argument("--topic", default="ai-agents")
    parser.add_argument("--language", choices=["en", "zh"], default="en")
    parser.add_argument("--no-llm", action="store_true", help="deterministic template only")
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    settings = load_settings()
    settings = settings.model_copy(
        update={"report": settings.report.model_copy(update={"language": args.language})}
    )
    if args.no_llm:
        settings = settings.model_copy(
            update={"pipeline": settings.pipeline.model_copy(update={"llm": "off"})}
        )

    run_id = args.run_id or f"check-report-{uuid.uuid4().hex[:8]}"
    result = run_graph(settings, args.topic, run_id=run_id)
    if result.get("state") != "succeeded":
        print(json.dumps({"ok": False, "run_id": run_id, "state": result.get("state")}, indent=2))
        return 1

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT content_md, claims_json, sections_json, language, generated_by, word_count"
                    " FROM reports WHERE run_id = :rid ORDER BY created_at DESC LIMIT 1"
                ),
                {"rid": run_id},
            ).first()
            papers = conn.execute(text("SELECT COUNT(*) FROM papers")).scalar_one()
    finally:
        engine.dispose()

    if row is None:
        print(json.dumps({"ok": False, "run_id": run_id, "error": "no report"}, indent=2))
        return 1

    content, claims_json, sections_json, language, generated_by, word_count = row
    claims = json.loads(claims_json or "[]")
    sections = json.loads(sections_json or "[]")
    cited = [claim for claim in claims if claim.get("citations")]
    problems: list[str] = []
    if not claims:
        problems.append("no claims")
    if not sections:
        problems.append("no sections")
    if language != args.language:
        problems.append(f"language mismatch: {language}")
    for section in sections:
        if section.get("kind") == "deep_dive" and not section.get("claim_indexes"):
            problems.append(f"{section.get('id')}: no claim_indexes")
        for match in re.finditer(r"\[C(\d+)\]", section.get("body") or ""):
            if int(match.group(1)) > len(claims):
                problems.append(f"{section.get('id')}: unresolved [C{match.group(1)}]")

    thin = len(claims) <= 1 or len(content or "") < 300
    summary = {
        "ok": not problems,
        "run_id": run_id,
        "language": language,
        "generated_by": generated_by,
        "papers_in_db": int(papers),
        "claims": len(claims),
        "cited_claims": len(cited),
        "sections": len(sections),
        "word_count": int(word_count or len(str(content).split())),
        "thin": thin,
        "problems": problems,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if thin:
        print(
            "WARN: thin report. If the DB only has a few fixture papers (e.g. E2E-P*), "
            "this is expected; seed or sync real papers first."
        )
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())

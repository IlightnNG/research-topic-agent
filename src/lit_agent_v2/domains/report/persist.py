"""Report persistence for v2 S3."""

from __future__ import annotations

from datetime import UTC, datetime

from lit_agent_v2.domains.report.write import ReportDraft
from lit_agent_v2.storage.db import Database

__all__ = ["persist_report"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def persist_report(db: Database, *, run_id: str, topic_id: str, draft: ReportDraft) -> str:
    report_id = f"{run_id}:{draft.content_sha}"
    with db.connect() as conn:
        for claim in draft.claims:
            conn.execute(
                "INSERT OR REPLACE INTO claims"
                "(claim_id,run_id,paper_id,text,quote,section,page,support,confidence)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    claim["claim_id"],
                    run_id,
                    claim["paper_id"],
                    claim["text"],
                    claim["quote"],
                    claim.get("section"),
                    claim.get("page"),
                    "supported",
                    claim.get("confidence", 0.5),
                ),
            )
        conn.execute(
            "INSERT INTO reports"
            "(report_id,run_id,topic_id,title,content_md,content_sha,state,word_count,"
            "n_claims,metrics_json,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                report_id,
                run_id,
                topic_id,
                draft.title,
                draft.content_md,
                draft.content_sha,
                draft.state,
                draft.word_count,
                len(draft.claims),
                None,
                _now(),
            ),
        )
        for order, section in enumerate(draft.sections):
            conn.execute(
                "INSERT INTO report_sections"
                "(report_id,section_id,kind,title,body,claim_indexes_json,ord)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    report_id,
                    section.section_id,
                    section.kind,
                    section.title,
                    section.body,
                    str(section.claim_indexes),
                    order,
                ),
            )
            for index in section.claim_indexes:
                if index < 0 or index >= len(draft.claims):
                    continue
                claim = draft.claims[index]
                conn.execute(
                    "INSERT INTO citations(report_id,section_id,claim_id,paper_id,quote)"
                    " VALUES (?,?,?,?,?)",
                    (report_id, section.section_id, claim["claim_id"], claim["paper_id"], claim["quote"]),
                )
    return report_id

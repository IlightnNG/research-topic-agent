"""Report source resolution (Phase 3.5 / S3).

The source node turns a topic + focus into a bounded set of local papers. It
does not call the legacy graph; retrieval is a domain tool.
"""

from __future__ import annotations

from sqlalchemy import text

from lit_agent.agents.retrieval import tokens
from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine

__all__ = ["resolve_report_papers"]


def resolve_report_papers(
    settings: Settings,
    topic_id: str,
    *,
    limit: int = 100,
    focus_hint: str | None = None,
    paper_ids: list[str] | None = None,
) -> list[str]:
    if paper_ids:
        return list(dict.fromkeys(paper_ids))[: max(1, limit)]

    from lit_agent.eval import faultinject

    if faultinject.is_active("empty_retrieval"):
        return []

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            scope = conn.execute(
                text("SELECT scope_statement FROM topics WHERE id=:t"), {"t": topic_id}
            ).scalar_one_or_none() or ""
            rows = conn.execute(
                text(
                    "SELECT paper_id, title, COALESCE(abstract,'') FROM papers"
                    " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)"
                )
            ).all()
    finally:
        engine.dispose()

    wanted = tokens(f"{scope} {focus_hint or ''}")
    scored: list[tuple[int, str]] = []
    for paper_id, title, abstract in rows:
        overlap = len(wanted & tokens(f"{title} {abstract}"))
        scored.append((overlap, str(paper_id)))
    # Stable order: relevance first, then paper id.
    scored.sort(key=lambda item: (-item[0], item[1]))
    return [paper_id for _score, paper_id in scored[: max(1, limit)]]

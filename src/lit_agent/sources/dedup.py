"""三段式去重落库 + 引用投影（guide §3 / Step 1.8）。

- `run_dedup`：读 SQLite 全量论文 → `dedup_papers`（自 Phase 0 迁移）→ 写 `paper_merges`
  与 `papers.merged_ids_json`；**不删除任何记录**（ADR-0001）。
- `project_citations`：引用只存在于 `papers_raw`（OpenAlex 原始 JSON）；投影时用
  `papers.source_id` 建 W-id → canonical 映射，只写"两端都在语料内"的边。
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.repo import citations as citation_repo
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.models.paper import Paper
from lit_agent.sources.normalize import dedup_papers

__all__ = ["project_citations", "run_dedup"]


def _load_models(settings: Settings) -> list[Paper]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT paper_id, title, abstract, source, source_id, venue_id, venue_name,"
                    " year, is_oa, language, cited_by_count FROM papers ORDER BY paper_id"
                )
            ).all()
    finally:
        engine.dispose()
    papers: list[Paper] = []
    for row in rows:
        data = dict(row._mapping)
        papers.append(
            Paper(
                paper_id=data["paper_id"],
                title=data["title"],
                abstract=data["abstract"] or "",
                source=data["source"],
                source_id=data["source_id"],
                venue=data["venue_name"],
                venue_id=data["venue_id"],
                year=data["year"],
                is_oa=bool(data["is_oa"]),
                language=data["language"],
                cited_by_count=data["cited_by_count"],
            )
        )
    return papers


def run_dedup(
    settings: Settings, *, run_id: str | None = None, fuzzy_min: float = 0.9
) -> dict[str, Any]:
    """执行去重并落库，返回合并对与统计。"""
    papers = _load_models(settings)
    result = dedup_papers(papers, fuzzy_min=fuzzy_min)
    merges = [
        (canonical, merged, "fingerprint")
        for canonical, merged_ids in result.merged.items()
        for merged in merged_ids
    ]

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            citation_repo.add_merges(conn, merges, run_id=run_id)
            for canonical, merged_ids in result.merged.items():
                paper_repo.set_merged_ids(conn, canonical, merged_ids)
    finally:
        engine.dispose()

    return {
        "input": len(papers),
        "unique": len(result.unique),
        "merged_pairs": len(merges),
        "merged": result.merged,
        "stats": result.stats,
    }


def project_citations(settings: Settings, *, run_id: str | None = None) -> dict[str, Any]:
    """把 `papers_raw.referenced_works` 投影成 `citations`（只收语料内两端）。"""
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            w_to_canonical = {
                str(row[0]): str(row[1])
                for row in conn.execute(text("SELECT source_id, paper_id FROM papers")).all()
                if row[0]
            }
            raws = conn.execute(
                text("SELECT source_id, raw_json FROM papers_raw ORDER BY raw_id")
            ).all()
            before = citation_repo.count(conn)
    finally:
        engine.dispose()

    pairs: list[tuple[str, str]] = []
    papers_with_refs = 0
    for source_id, raw_json in raws:
        citing = w_to_canonical.get(str(source_id))
        if not citing:
            continue
        try:
            payload = json.loads(raw_json)
        except (TypeError, ValueError):
            continue
        refs = payload.get("referenced_works") or []
        if refs:
            papers_with_refs += 1
        for ref in refs:
            cited = w_to_canonical.get(str(ref).replace("https://openalex.org/", ""))
            if cited and cited != citing:
                pairs.append((citing, cited))

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            attempted = citation_repo.insert_ignore_many(conn, pairs, run_id=run_id)
            after = citation_repo.count(conn)
    finally:
        engine.dispose()

    return {
        "papers_with_refs": papers_with_refs,
        "candidate_edges": len(pairs),
        "attempted": attempted,
        "edges_added": after - before,
        "edges_total": after,
    }

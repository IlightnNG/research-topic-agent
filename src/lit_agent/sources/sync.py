"""一次同步的编排：adapter → SQLite（papers / papers_raw / sync_state）。

职责边界：
- 只做"抓取 + 落源数据"，**不做去重/投影**（Step 1.8）；
- 因此 `citations` 在此阶段仍为 0（引用需要 canonical 映射，见 1.8 的投影）。
- 幂等：`papers` 按 `paper_id` upsert；`papers_raw` 按 `(source, source_id, content_sha)` 去重。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from lit_agent.config import Settings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import sync as sync_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.errors import E_CONFIG_INVALID, E_SRC_NO_SELECTOR, LitError
from lit_agent.models.paper import Paper
from lit_agent.sources.base import SourceAdapter
from lit_agent.sources.openalex import OpenAlexAdapter
from lit_agent.sources.whitelist import selector_key

__all__ = ["sync_topic"]


def _content_sha(work: dict[str, Any]) -> str:
    canonical = json.dumps(work, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _existing_ids(settings: Settings) -> set[str]:
    from sqlalchemy import text

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(text("SELECT paper_id FROM papers")).all()
    finally:
        engine.dispose()
    return {str(row[0]) for row in rows}


def sync_topic(
    settings: Settings,
    topic_id: str,
    *,
    limit: int | None = None,
    adapter: SourceAdapter | None = None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """按 topic 的 openalex selector 同步一次，返回计数（含 `papers_new`）。"""
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic = topic_repo.get(conn, topic_id)
            if topic is None:
                raise LitError(
                    E_CONFIG_INVALID,
                    f"topic 不存在：{topic_id}（先 `lit-agent db upgrade` 并写入 topic）",
                    context={"topic_id": topic_id},
                )
            sources = topic_repo.get_sources(conn, topic_id)
            if not sources:
                raise LitError(
                    E_SRC_NO_SELECTOR,
                    f"topic {topic_id} 没有配置任何源 selector",
                    context={"topic_id": topic_id},
                )
            # 单源分派：配了 openalex 就用它，否则按名字取第一个（如 arxiv）。
            # 多源并行/合并留 P4（每源独立游标，需要合并报表口径）。
            source_name = "openalex" if "openalex" in sources else sorted(sources)[0]
            selector = sources[source_name]
            key = selector_key(selector)
            state = sync_repo.get(conn, source_name, key)
            since = None
            if state is not None:
                since = state._mapping.get("last_since")
    finally:
        engine.dispose()

    # 默认窗口：selector 没写 from_year 时取**最近 90 天**。
    # 不能因为"没配日期"就去拉该 venue 的全量历史（NeurIPS 一家就近 2 万篇，
    # 既慢又会把 OpenAlex 免费日配额打穿——2026-10-19 实测 401 就是这么来的）。
    start = since
    if not start:
        if selector.get("from_year"):
            start = f"{int(selector['from_year'])}-01-01"
        else:
            from datetime import UTC, datetime, timedelta

            start = (datetime.now(UTC) - timedelta(days=90)).date().isoformat()
    if adapter is not None:
        chosen = adapter
    elif source_name == "arxiv":
        from lit_agent.sources.arxiv import ArxivAdapter

        chosen = ArxivAdapter()
    else:
        chosen = OpenAlexAdapter.from_settings(settings)
    before = _existing_ids(settings)

    fetched_works: list[dict[str, Any]] = []
    papers: list[Paper] = []
    if hasattr(chosen, "fetch_works"):
        for work in chosen.fetch_works(since=start, selector=selector, limit=limit):  # type: ignore[attr-defined]
            fetched_works.append(work)
            papers.append(chosen_paper(work))
    else:  # 只有 fetch 的适配器（如 arXiv）
        papers = list(chosen.fetch(since=start, selector=selector, limit=limit))

    engine = make_engine(settings)
    dial = {"source": source_name, "selector": key}
    try:
        with connect(engine, immediate=True) as conn:
            paper_repo.upsert_many(conn, papers)
            if fetched_works:
                paper_repo.insert_raw_many(
                    conn,
                    [
                        {
                            "source": source_name,
                            "source_id": _work_id(work),
                            "run_id": run_id,
                            "content_sha": _content_sha(work),
                            "raw_json": json.dumps(work, ensure_ascii=False, default=str),
                        }
                        for work in fetched_works
                    ],
                )
            sync_repo.set_cursor(conn, source_name, key, cursor=None, since=start, status="idle")
    finally:
        engine.dispose()

    after = _existing_ids(settings)
    new_ids = after - before
    return {
        "source": source_name,
        "topic_id": topic_id,
        "selector_key": dial["selector"],
        "since": start,
        "fetched": len(papers),
        "papers_new": len(new_ids),
        "papers_updated": max(0, len(papers) - len(new_ids)),
        "raw_records": len(fetched_works),
    }


def chosen_paper(work: dict[str, Any]) -> Paper:
    from lit_agent.sources.normalize import openalex_work_to_paper

    return openalex_work_to_paper(work)


def _work_id(work: dict[str, Any]) -> str:
    return str(work.get("id") or work.get("doi") or work.get("title") or "").replace(
        "https://openalex.org/", ""
    )

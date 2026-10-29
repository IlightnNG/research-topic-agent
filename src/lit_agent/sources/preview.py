"""Source preview（3.3 / S1）：按 selector 取一小批论文，供用户确认范围。"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from lit_agent.config import Settings
from lit_agent.errors import E_SRC_NO_SELECTOR, LitError
from lit_agent.sources.normalize import openalex_work_to_paper
from lit_agent.sources.openalex import OpenAlexAdapter

__all__ = ["preview_selector"]


def _since(selector: dict[str, Any]) -> str:
    if selector.get("from_year"):
        return f"{int(selector['from_year'])}-01-01"
    return (datetime.now(UTC) - timedelta(days=90)).date().isoformat()


def preview_selector(
    settings: Settings,
    selector: dict[str, Any],
    *,
    limit: int = 10,
    adapter: Any | None = None,
) -> dict[str, Any]:
    if not (selector.get("venue_ids") or selector.get("queries")):
        raise LitError(
            E_SRC_NO_SELECTOR,
            "preview needs venue_ids or queries",
            context={"selector": selector},
        )
    limit = max(1, min(int(limit), 50))
    since = _since(selector)
    chosen = adapter or OpenAlexAdapter.from_settings(settings)
    works = list(chosen.fetch_works(since=since, selector=selector, limit=limit))
    items: list[dict[str, Any]] = []
    for work in works:
        paper = openalex_work_to_paper(work)
        items.append(
            {
                "paper_id": paper.paper_id,
                "title": paper.title,
                "year": paper.year,
                "source": paper.source,
            }
        )
    return {"selector": selector, "since": since, "sample_count": len(items), "items": items}

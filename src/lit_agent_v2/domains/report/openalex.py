"""OpenAlex source adapter for v2 (no legacy imports)."""

from __future__ import annotations

from typing import Any

import httpx

from lit_agent_v2.contracts.report import Paper

__all__ = ["OpenAlexAdapter"]

_API = "https://api.openalex.org/works"


def _abstract(index: dict[str, list[int]] | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in index.items():
        positions.extend((pos, word) for pos in indexes)
    return " ".join(word for _pos, word in sorted(positions))


class OpenAlexAdapter:
    def __init__(self, *, client: httpx.Client | None = None, mailto: str | None = None) -> None:
        self.client = client or httpx.Client(timeout=30.0)
        self.mailto = mailto

    def fetch(
        self,
        query: str,
        *,
        limit: int = 100,
        from_year: int | None = None,
        venue_ids: list[str] | None = None,
    ) -> list[Paper]:
        filters = []
        if from_year:
            filters.append(f"from_publication_date:{from_year}-01-01")
        if venue_ids:
            filters.append("primary_location.source.id:" + "|".join(venue_ids))
        params: dict[str, Any] = {
            "search": query,
            "per-page": min(200, max(1, limit)),
            "page": 1,
        }
        if filters:
            params["filter"] = ",".join(filters)
        if self.mailto:
            params["mailto"] = self.mailto
        response = self.client.get(_API, params=params)
        response.raise_for_status()
        payload = response.json()
        papers: list[Paper] = []
        for item in payload.get("results", [])[:limit]:
            location = item.get("primary_location") or {}
            source = location.get("source") or {}
            best = item.get("best_oa_location") or {}
            authors = [
                str((entry.get("author") or {}).get("display_name") or "").strip()
                for entry in item.get("authorships") or []
            ]
            authors = [name for name in authors if name]
            landing = str(location.get("landing_page_url") or "")
            papers.append(
                Paper(
                    paper_id=str(item.get("id") or "").rsplit("/", 1)[-1],
                    title=str(item.get("title") or ""),
                    abstract=_abstract(item.get("abstract_inverted_index")),
                    url=str(item.get("doi") or landing or item.get("id") or ""),
                    source="openalex",
                    venue=str(source.get("display_name") or ""),
                    year=item.get("publication_year"),
                    pdf_url=str(best.get("pdf_url") or location.get("pdf_url") or ""),
                    html_url=landing,
                    authors=authors,
                )
            )
        return [paper for paper in papers if paper.paper_id]

"""内置工具：OpenAlex 检索（原子能力，不做编排）。"""

from __future__ import annotations

from typing import Any

import httpx

from lit_agent.sources.openalex import OpenAlexAdapter
from lit_agent.tools.registry import Tool

__all__ = ["build_tool", "run"]


def run(
    *,
    selector: dict[str, Any],
    since: str | None = None,
    limit: int = 10,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    adapter = OpenAlexAdapter(client=client)
    return [
        paper.model_dump(mode="json")
        for paper in adapter.fetch(since=since, selector=selector, limit=limit)
    ]


def build_tool() -> Tool:
    return Tool(
        name="openalex_search",
        run=run,
        description="Search OpenAlex works by venue whitelist and date window",
        parameters={"selector": "object", "since": "string?", "limit": "integer"},
        timeout_s=30.0,
    )

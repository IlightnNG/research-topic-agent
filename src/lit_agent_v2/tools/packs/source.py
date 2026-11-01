"""Source tools backed by the existing OpenAlex/PDF adapters."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.research.openalex import OpenAlexAdapter
from lit_agent_v2.research.pdf import download_html_text, download_pdf_text

__all__ = ["build_source_tools", "fetch_html", "fetch_pdf", "search_openalex"]


def search_openalex(query: str, limit: int = 100, from_year: int | None = None) -> dict[str, Any]:
    papers = OpenAlexAdapter().fetch(query, limit=limit, from_year=from_year)
    return {"papers": [paper.__dict__ for paper in papers], "count": len(papers)}


def fetch_pdf(url: str) -> dict[str, Any]:
    text = download_pdf_text(url)
    return {"text": text, "chars": len(text)}


def fetch_html(url: str) -> dict[str, Any]:
    text = download_html_text(url)
    return {"text": text, "chars": len(text)}


def build_source_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            "source.search",
            "Search OpenAlex for papers.",
            {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "limit": {"type": "integer"},
                    "from_year": {"type": "integer"},
                },
                "required": ["query"],
            },
            {"type": "object"},
            timeout_s=60.0,
            handler=lambda args: search_openalex(
                args["query"], int(args.get("limit", 100)), args.get("from_year")
            ),
        ),
        ToolSpec(
            "source.fetch_pdf",
            "Download a PDF and extract its text.",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            {"type": "object"},
            timeout_s=60.0,
            handler=lambda args: fetch_pdf(args["url"]),
        ),
        ToolSpec(
            "source.fetch_html",
            "Download an HTML page and extract text.",
            {
                "type": "object",
                "properties": {"url": {"type": "string"}},
                "required": ["url"],
            },
            {"type": "object"},
            timeout_s=60.0,
            handler=lambda args: fetch_html(args["url"]),
        ),
    ]

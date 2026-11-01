"""Corpus tools: stats, dedupe, local store."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec

__all__ = [
    "build_corpus_tools",
    "corpus_dedupe",
    "corpus_papers",
    "corpus_stats",
    "corpus_store",
]


def _papers(root: str | Path) -> list[dict[str, Any]]:
    path = Path(root) / "papers.jsonl"
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def corpus_stats(root: str | Path) -> dict[str, Any]:
    papers = _papers(root)
    fulltext_dir = Path(root) / "fulltext"
    fulltext = len(list(fulltext_dir.glob("*.txt"))) if fulltext_dir.exists() else 0
    return {
        "papers": len(papers),
        "fulltext": fulltext,
        "fulltext_ratio": fulltext / len(papers) if papers else 0.0,
        "with_abstract": sum(1 for paper in papers if paper.get("abstract")),
    }


def corpus_dedupe(papers: list[dict[str, Any]]) -> dict[str, Any]:
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for paper in papers:
        key = str(paper.get("paper_id") or "").strip().lower()
        title = str(paper.get("title") or "").strip().lower()
        marker = key or title
        if not marker or marker in seen:
            continue
        seen.add(marker)
        unique.append(paper)
    return {"papers": unique, "kept": len(unique), "removed": len(papers) - len(unique)}


def corpus_papers(root: str | Path, limit: int = 20) -> dict[str, Any]:
    papers = _papers(root)[: max(1, limit)]
    return {"papers": papers, "count": len(papers)}


def corpus_store(root: str | Path, papers: list[dict[str, Any]]) -> dict[str, Any]:
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    with (path / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for paper in papers:
            handle.write(json.dumps(paper, ensure_ascii=False) + "\n")
    return {"root": str(path), "papers": len(papers)}


def build_corpus_tools() -> list[ToolSpec]:
    return [
        ToolSpec(
            "corpus.stats",
            "Count papers, fulltext, and abstract coverage in a local corpus.",
            {"type": "object", "properties": {"root": {"type": "string"}}, "required": ["root"]},
            {"type": "object"},
            handler=lambda args: corpus_stats(args["root"]),
        ),
        ToolSpec(
            "corpus.papers",
            "Read papers (metadata and abstracts) from a local corpus.",
            {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "limit": {"type": "integer"},
                },
                "required": ["root"],
            },
            {"type": "object"},
            handler=lambda args: corpus_papers(args["root"], int(args.get("limit", 20))),
        ),
        ToolSpec(
            "corpus.dedupe",
            "Deduplicate papers by paper_id or normalized title.",
            {
                "type": "object",
                "properties": {"papers": {"type": "array", "items": {"type": "object"}}},
                "required": ["papers"],
            },
            {"type": "object"},
            handler=lambda args: corpus_dedupe(args["papers"]),
        ),
        ToolSpec(
            "corpus.store",
            "Persist papers.jsonl in a corpus directory.",
            {
                "type": "object",
                "properties": {
                    "root": {"type": "string"},
                    "papers": {"type": "array", "items": {"type": "object"}},
                },
                "required": ["root", "papers"],
            },
            {"type": "object"},
            side_effect=True,
            handler=lambda args: corpus_store(args["root"], args["papers"]),
        ),
    ]

"""Local corpus ingestion for v2 S2."""

from __future__ import annotations

import json
from pathlib import Path

from lit_agent_v2.contracts.report import Paper

__all__ = ["LocalCorpus"]


class LocalCorpus:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.papers_path = self.root / "papers.jsonl"
        self.fulltext_dir = self.root / "fulltext"

    def papers(self) -> list[Paper]:
        if not self.papers_path.exists():
            return []
        items: list[Paper] = []
        for line in self.papers_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            raw = json.loads(line)
            paper = Paper(
                paper_id=str(raw["paper_id"]),
                title=str(raw.get("title") or ""),
                abstract=str(raw.get("abstract") or ""),
                url=str(raw.get("url") or ""),
                source=str(raw.get("source") or "local"),
                venue=str(raw.get("venue") or ""),
                year=raw.get("year"),
                pdf_url=str(raw.get("pdf_url") or ""),
                html_url=str(raw.get("html_url") or ""),
                authors=[str(name) for name in raw.get("authors") or []],
            )
            text_path = self.fulltext_dir / f"{paper.paper_id}.txt"
            if text_path.exists():
                paper.fulltext = text_path.read_text(encoding="utf-8")
            items.append(paper)
        return items


class IngestService:
    """Fetch via an adapter, persist a local corpus, optionally enrich full text."""

    def __init__(self, adapter: object, root: str | Path) -> None:
        self.adapter = adapter
        self.root = Path(root)

    def ingest(
        self,
        query: str,
        *,
        limit: int = 100,
        from_year: int | None = None,
        venue_ids: list[str] | None = None,
        fulltext_limit: int = 0,
    ) -> LocalCorpus:
        papers = self.adapter.fetch(
            query, limit=limit, from_year=from_year, venue_ids=venue_ids
        )
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / "fulltext").mkdir(exist_ok=True)
        with (self.root / "papers.jsonl").open("w", encoding="utf-8") as handle:
            for paper in papers:
                handle.write(json.dumps(paper.__dict__, ensure_ascii=False) + "\n")
        if fulltext_limit:
            from lit_agent_v2.domains.report.pdf import download_html_text, download_pdf_text

            for paper in papers:
                if len(list((self.root / "fulltext").glob("*.txt"))) >= fulltext_limit:
                    break
                text = ""
                if paper.pdf_url:
                    try:
                        text = download_pdf_text(paper.pdf_url)
                    except Exception:
                        text = ""
                if not text and paper.html_url:
                    try:
                        text = download_html_text(paper.html_url)
                    except Exception:
                        text = ""
                if text:
                    (self.root / "fulltext" / f"{paper.paper_id}.txt").write_text(
                        text, encoding="utf-8"
                    )
        return LocalCorpus(self.root)

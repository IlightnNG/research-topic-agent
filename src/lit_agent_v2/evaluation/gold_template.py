"""M5-P02: generate human annotation templates from real corpora.

Templates intentionally contain no gold claims. They are drafts, not a dataset.
"""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

__all__ = ["build_gold_template"]

COLUMNS = [
    "case_id",
    "topic_id",
    "paper_id",
    "title",
    "authors",
    "venue",
    "year",
    "direction_id",
    "direction_name",
    "relevance_1_5",
    "claim_1_text",
    "claim_1_quote",
    "claim_1_type",
    "claim_1_importance_1_5",
    "claim_2_text",
    "claim_2_quote",
    "claim_2_type",
    "claim_2_importance_1_5",
]


def build_gold_template(
    corpora: dict[str, Path | str],
    output_dir: Path | str,
    *,
    limit: int = 100,
    force: bool = False,
) -> Path:
    out = Path(output_dir)
    dataset_path = out / "dataset.json"
    if dataset_path.exists() and not force:
        raise FileExistsError(f"template already exists: {dataset_path}")
    out.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []
    rows: list[dict] = []
    for index, (topic_id, corpus_root) in enumerate(corpora.items(), start=1):
        case_id = f"case-{index:03d}"
        papers = _read_papers(Path(corpus_root), limit=limit)
        if not papers:
            raise ValueError(f"no papers in corpus: {corpus_root}")
        cases.append(
            {
                "case_id": case_id,
                "topic_id": topic_id,
                "corpus_root": str(Path(corpus_root)),
                "limit": limit,
                "focus_hint": topic_id,
                "annotation_status": "unlabeled",
                "gold_directions": [],
                "papers": [_template_paper(paper) for paper in papers],
            }
        )
        rows.extend(_annotation_rows(case_id, topic_id, papers))
    payload = {
        "schema_version": 2,
        "name": "report-gold",
        "version": "0.1-draft",
        "status": "draft",
        "cases": cases,
    }
    dataset_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    sheet = out / "annotation-sheet.csv"
    with sheet.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return dataset_path


def _read_papers(root: Path, *, limit: int) -> list[dict]:
    path = root / "papers.jsonl"
    if not path.exists():
        raise FileNotFoundError(path)
    papers: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            papers.append(json.loads(line))
        if len(papers) >= limit:
            break
    return papers


def _template_paper(paper: dict) -> dict:
    return {
        "paper_id": str(paper["paper_id"]),
        "title": str(paper.get("title") or ""),
        "authors": [str(name) for name in paper.get("authors") or []],
        "venue": str(paper.get("venue") or ""),
        "year": paper.get("year"),
        "relevance": 0,
        "source_text": str(paper.get("fulltext") or paper.get("abstract") or ""),
        "claims": [],
    }


def _annotation_rows(case_id: str, topic_id: str, papers: Iterable[dict]) -> list[dict]:
    rows = []
    for paper in papers:
        rows.append(
            {
                "case_id": case_id,
                "topic_id": topic_id,
                "paper_id": str(paper["paper_id"]),
                "title": str(paper.get("title") or ""),
                "authors": "; ".join(str(name) for name in paper.get("authors") or []),
                "venue": str(paper.get("venue") or ""),
                "year": paper.get("year") or "",
                "direction_id": "",
                "direction_name": "",
                "relevance_1_5": "",
                "claim_1_text": "",
                "claim_1_quote": "",
                "claim_1_type": "",
                "claim_1_importance_1_5": "",
                "claim_2_text": "",
                "claim_2_quote": "",
                "claim_2_type": "",
                "claim_2_importance_1_5": "",
            }
        )
    return rows

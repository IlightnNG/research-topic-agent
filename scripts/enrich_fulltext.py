"""Best-effort fulltext enrichment for a local corpus.

Usage:
  python scripts/enrich_fulltext.py --corpus D:\\lit-agent-store\\... --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from lit_agent_v2.research.pdf import download_html_text, download_pdf_text

__all__ = ["enrich"]


def _papers(corpus: Path) -> list[dict[str, Any]]:
    path = corpus / "papers.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _attempt(paper: dict[str, Any], corpus: Path) -> dict[str, Any]:
    paper_id = str(paper.get("paper_id") or "")
    target = corpus / "fulltext" / f"{paper_id}.txt"
    if target.exists() and target.stat().st_size > 500:
        return {"paper_id": paper_id, "ok": True, "chars": target.stat().st_size, "source": "existing"}
    errors: list[str] = []
    for source, url in (
        ("pdf", str(paper.get("pdf_url") or "")),
        ("html", str(paper.get("html_url") or "")),
    ):
        if not url:
            continue
        try:
            text = download_pdf_text(url) if source == "pdf" else download_html_text(url)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"{source}:{type(exc).__name__}")
            continue
        if len(text.strip()) < 500:
            errors.append(f"{source}:too_short")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        return {"paper_id": paper_id, "ok": True, "chars": len(text), "source": source}
    return {"paper_id": paper_id, "ok": False, "errors": errors}


def enrich(corpus: Path, *, limit: int = 20, workers: int = 4) -> dict[str, Any]:
    papers = _papers(corpus)
    pending = [
        paper
        for paper in papers
        if not (corpus / "fulltext" / f"{paper.get('paper_id')}.txt").exists()
    ][:limit]
    rows = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_attempt, paper, corpus) for paper in pending]
        for future in as_completed(futures):
            rows.append(future.result())
    fulltext_dir = corpus / "fulltext"
    fulltext = len(list(fulltext_dir.glob("*.txt"))) if fulltext_dir.exists() else 0
    return {
        "requested": len(pending),
        "succeeded": sum(1 for row in rows if row.get("ok")),
        "failed": sum(1 for row in rows if not row.get("ok")),
        "papers": len(papers),
        "fulltext": fulltext,
        "fulltext_ratio": fulltext / len(papers) if papers else 0.0,
        "rows": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("D:/lit-agent-store/fulltext-enrich.json"))
    args = parser.parse_args()
    result = enrich(args.corpus, limit=args.limit, workers=args.workers)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "rows"}, ensure_ascii=False))
    return 0 if result["succeeded"] else 1


if __name__ == "__main__":
    sys.exit(main())

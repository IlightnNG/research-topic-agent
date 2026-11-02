"""Prepare a 100-paper corpus with enough full text for the full-chain demo.

Downloads PDFs for papers that have a `pdf_url`, extracts text, and writes a
new corpus directory. The original corpus is not modified.

Usage:

    . .\\scripts\\env.ps1
    uv run python scripts\\prepare_fulltext.py `
        --corpus D:\\lit-agent-store\\v2-eval\\gold\\corpora\\agents `
        --out D:\\lit-agent-store\\v2-eval\\gold\\corpora\\agents-fulltext `
        --target 35
"""

from __future__ import annotations

import argparse
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

from lit_agent_v2.research.pdf import extract_pdf_text

DEFAULT_CORPUS = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents")
DEFAULT_OUT = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext")


def _download(paper: dict) -> tuple[str, str]:
    paper_id = str(paper.get("paper_id") or "")
    url = str(paper.get("pdf_url") or "")
    if not paper_id or not url:
        return paper_id, ""
    try:
        response = httpx.get(url, follow_redirects=True, timeout=60.0)
        response.raise_for_status()
        text = extract_pdf_text(response.content)
        return paper_id, text
    except Exception as exc:  # noqa: BLE001
        print(f"skip {paper_id}: {type(exc).__name__}: {exc}")
        return paper_id, ""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--target", type=int, default=35)
    args = parser.parse_args()

    papers = [
        json.loads(line)
        for line in (args.corpus / "papers.jsonl").read_text(encoding="utf-8").splitlines()
        if line
    ]
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "fulltext").mkdir(exist_ok=True)
    shutil.copyfile(args.corpus / "papers.jsonl", args.out / "papers.jsonl")

    candidates = [paper for paper in papers if paper.get("pdf_url")][: max(args.target * 2, 40)]
    succeeded = 0
    with ThreadPoolExecutor(max_workers=6) as executor:
        futures = [executor.submit(_download, paper) for paper in candidates]
        for future in as_completed(futures):
            paper_id, text = future.result()
            if not paper_id or len(text.strip()) < 200:
                continue
            (args.out / "fulltext" / f"{paper_id}.txt").write_text(text, encoding="utf-8")
            succeeded += 1
            if succeeded >= args.target:
                for pending in futures:
                    pending.cancel()
                break
            print(f"fulltext {succeeded}/{args.target}: {paper_id}")

    print(
        json.dumps(
            {
                "papers": len(papers),
                "fulltext": succeeded,
                "ratio": round(succeeded / len(papers), 3),
                "out": str(args.out),
            }
        )
    )
    return 0 if succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())

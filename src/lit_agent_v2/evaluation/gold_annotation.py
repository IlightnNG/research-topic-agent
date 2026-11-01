"""Compile filled annotation CSV into a validated gold dataset."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from lit_agent_v2.evaluation.gold import GoldDataset

__all__ = ["compile_annotations"]

_TYPES = {"finding", "method", "dataset", "limitation", "background"}


def compile_annotations(
    template_path: Path | str,
    annotations_path: Path | str,
    output_path: Path | str,
    *,
    status: str = "annotated",
) -> GoldDataset:
    template = json.loads(Path(template_path).read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in template.get("cases") or []}
    papers = {
        (case["case_id"], paper["paper_id"]): paper
        for case in template.get("cases") or []
        for paper in case.get("papers") or []
    }
    with Path(annotations_path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    seen: set[tuple[str, str]] = set()
    grouped: dict[str, dict[str, list[str]]] = {case_id: {} for case_id in cases}
    compiled: dict[tuple[str, str], dict] = {}

    for row in rows:
        case_id = str(row.get("case_id") or "").strip()
        paper_id = str(row.get("paper_id") or "").strip()
        key = (case_id, paper_id)
        if key not in papers:
            raise ValueError(f"unknown case/paper: {case_id}/{paper_id}")
        if key in seen:
            raise ValueError(f"duplicate annotation row: {case_id}/{paper_id}")
        seen.add(key)
        template_paper = papers[key]
        relevance = _int(row.get("relevance_1_5"), "relevance", 1, 5)
        direction_id = str(row.get("direction_id") or "").strip()
        if not direction_id:
            raise ValueError(f"{paper_id}: missing direction_id")
        claims = []
        for index in (1, 2):
            text = str(row.get(f"claim_{index}_text") or "").strip()
            quote = str(row.get(f"claim_{index}_quote") or "").strip()
            if not text and not quote:
                continue
            if not text or not quote:
                raise ValueError(f"{paper_id}: incomplete claim {index}")
            if quote not in str(template_paper.get("source_text") or ""):
                raise ValueError(f"{paper_id}: claim {index} quote not verbatim")
            claim_type = str(row.get(f"claim_{index}_type") or "finding").strip()
            if claim_type not in _TYPES:
                raise ValueError(f"{paper_id}: invalid claim type {claim_type}")
            claims.append(
                {
                    "claim_id": f"{paper_id}-C{index}",
                    "paper_id": paper_id,
                    "text": text,
                    "quote": quote,
                    "claim_type": claim_type,
                    "importance": _int(
                        row.get(f"claim_{index}_importance_1_5"), "importance", 1, 5
                    ),
                }
            )
        if not claims:
            raise ValueError(f"{paper_id}: at least one claim required")
        compiled[key] = {
            "paper_id": paper_id,
            "title": template_paper.get("title") or "",
            "authors": template_paper.get("authors") or [],
            "venue": template_paper.get("venue") or "",
            "year": template_paper.get("year"),
            "relevance": relevance,
            "source_text": template_paper.get("source_text") or "",
            "claims": claims,
        }
        grouped[case_id].setdefault(direction_id, []).append(paper_id)

    missing = set(papers) - seen
    if missing:
        raise ValueError(f"missing annotation rows: {len(missing)}")
    output_cases = []
    for case_id, case in cases.items():
        output_cases.append(
            {
                **{key: case.get(key) for key in ("case_id", "topic_id", "corpus_root", "limit", "focus_hint")},
                "gold_directions": [
                    sorted(ids) for _direction, ids in sorted(grouped[case_id].items())
                ],
                "papers": [
                    compiled[(case_id, paper["paper_id"])]
                    for paper in case.get("papers") or []
                ],
            }
        )
    payload = {
        "schema_version": 2,
        "name": template.get("name") or "report-gold",
        "version": "1.0",
        "status": status,
        "cases": output_cases,
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    dataset = GoldDataset.load(output)
    dataset.assert_frozen(dataset.sha)
    return dataset


def _int(value: object, label: str, low: int, high: int) -> int:
    try:
        number = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid {label}: {value!r}") from exc
    if not low <= number <= high:
        raise ValueError(f"invalid {label}: {number}")
    return number

"""M5-P02: annotation template generation."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from lit_agent_v2.evaluation.gold_annotation import compile_annotations
from lit_agent_v2.evaluation.gold_prelabel import Annotator, annotate_template
from lit_agent_v2.evaluation.gold_template import build_gold_template


def _corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    with (root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(3):
            handle.write(
                json.dumps(
                    {
                        "paper_id": f"P{index}",
                        "title": f"Study {index}",
                        "abstract": "Tool routing improves agent success.",
                        "authors": ["Ada Lovelace"],
                        "venue": "ACL",
                        "year": 2025,
                    }
                )
                + "\n"
            )
    return root


def test_template_has_no_gold_claims(tmp_path: Path) -> None:
    path = build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "gold")
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["status"] == "draft"
    assert len(data["cases"]) == 1
    assert len(data["cases"][0]["papers"]) == 3
    assert all(not paper["claims"] for paper in data["cases"][0]["papers"])
    rows = list(csv.DictReader((tmp_path / "gold" / "annotation-sheet.csv").open(encoding="utf-8")))
    assert len(rows) == 3
    assert rows[0]["claim_1_text"] == ""
    assert rows[0]["relevance_1_5"] == ""


def test_template_does_not_overwrite(tmp_path: Path) -> None:
    build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "gold")
    with pytest.raises(FileExistsError):
        build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "gold")


def _fill_sheet(path: Path, *, bad_quote: bool = False) -> None:
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    for index, row in enumerate(rows):
        row["direction_id"] = "D1"
        row["direction_name"] = "Tool use"
        row["relevance_1_5"] = "4"
        row["claim_1_text"] = "Tool routing improves agent success."
        row["claim_1_quote"] = "bad" if bad_quote and index == 0 else "Tool routing improves agent success."
        row["claim_1_type"] = "finding"
        row["claim_1_importance_1_5"] = "4"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


def test_compile_annotations(tmp_path: Path) -> None:
    build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "gold")
    _fill_sheet(tmp_path / "gold" / "annotation-sheet.csv")
    dataset = compile_annotations(
        tmp_path / "gold" / "dataset.json",
        tmp_path / "gold" / "annotation-sheet.csv",
        tmp_path / "gold-final" / "dataset.json",
    )
    assert len(dataset.cases[0].papers) == 3
    assert dataset.cases[0].papers[0].claims[0].quote == "Tool routing improves agent success."
    assert len(dataset.cases[0].gold_directions) == 1


def test_compile_rejects_bad_quote(tmp_path: Path) -> None:
    build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "gold")
    _fill_sheet(tmp_path / "gold" / "annotation-sheet.csv", bad_quote=True)
    with pytest.raises(ValueError):
        compile_annotations(
            tmp_path / "gold" / "dataset.json",
            tmp_path / "gold" / "annotation-sheet.csv",
            tmp_path / "gold-final" / "dataset.json",
        )


class FakeAnnotatorClient:
    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        system = messages[0]["content"]
        user = __import__("json").loads(messages[1]["content"])
        if "Cluster papers" in system:
            return {
                "directions": [
                    {"direction_id": "D1", "name": "Tool", "paper_ids": ["P0"]},
                    {"direction_id": "D2", "name": "Retrieval", "paper_ids": ["P1"]},
                    {"direction_id": "D3", "name": "Planning", "paper_ids": ["P2"]},
                    {"direction_id": "D4", "name": "Memory", "paper_ids": []},
                    {"direction_id": "D5", "name": "Evaluation", "paper_ids": []},
                ]
            }, None
        papers = []
        for paper in user["papers"]:
            papers.append(
                {
                    "paper_id": paper["paper_id"],
                    "relevance": 4,
                    "claims": [
                        {
                            "text": "Tool routing improves agent success on benchmark tasks.",
                            "quote": "Tool routing improves agent success on benchmark tasks.",
                            "type": "finding",
                            "importance": 4,
                        }
                    ],
                }
            )
        return {"papers": papers}, None


def test_ai_prelabel(tmp_path: Path) -> None:
    build_gold_template({"agents": _corpus(tmp_path)}, tmp_path / "template")
    # template uses short source_text in the test corpus; make it long enough
    dataset_path = tmp_path / "template" / "dataset.json"
    data = json.loads(dataset_path.read_text(encoding="utf-8"))
    for paper in data["cases"][0]["papers"]:
        paper["source_text"] = "Tool routing improves agent success on benchmark tasks."
    dataset_path.write_text(json.dumps(data), encoding="utf-8")
    annotators = [
        Annotator("a", "fake-a", FakeAnnotatorClient(), "a"),
        Annotator("b", "fake-b", FakeAnnotatorClient(), "b"),
    ]
    meta = annotate_template(tmp_path / "template", tmp_path / "out", annotators=annotators)
    assert meta["status"] == "ai-prelabel"
    assert (tmp_path / "out" / "gold-a" / "dataset.json").exists()
    assert (tmp_path / "out" / "annotation-sheet-a.csv").exists()

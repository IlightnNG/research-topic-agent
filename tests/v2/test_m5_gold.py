"""M5-P02: gold schema and judge calibration."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lit_agent_v2.evaluation.calibration import (
    CalibrationSample,
    calibrate,
    cohen_kappa,
)
from lit_agent_v2.evaluation.gold import load_gold

DIMENSIONS = ["relevance", "coverage", "grounding", "synthesis", "readability", "actionability"]


def _gold(tmp_path: Path, *, bad_quote: bool = False) -> Path:
    papers = []
    directions = []
    for group in range(5):
        ids = []
        for index in range(4):
            pid = f"P{group}{index}"
            ids.append(pid)
            quote = "Tool routing improves agent success."
            if bad_quote and group == 0 and index == 0:
                quote = "not present"
            papers.append(
                {
                    "paper_id": pid,
                    "title": f"Study {pid}",
                    "authors": [f"Author {group}"],
                    "venue": "ACL",
                    "year": 2025,
                    "relevance": 4,
                    "source_text": "Tool routing improves agent success.",
                    "claims": [
                        {
                            "claim_id": f"{pid}-C1",
                            "paper_id": pid,
                            "text": "Tool routing improves agent success.",
                            "quote": quote,
                            "claim_type": "finding",
                            "importance": 4,
                        }
                    ],
                }
            )
        directions.append(ids)
    data = {
        "name": "gold",
        "version": "1.0",
        "cases": [
            {
                "case_id": "case-001",
                "topic_id": "agents",
                "corpus_root": str(tmp_path / "corpus"),
                "limit": 20,
                "gold_directions": directions,
                "papers": papers,
            }
        ],
    }
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_gold_load_and_freeze(tmp_path: Path) -> None:
    dataset = load_gold(_gold(tmp_path))
    assert len(dataset.cases) == 1
    assert dataset.cases[0].papers[0].claims[0].importance == 4
    dataset.assert_frozen(dataset.sha)
    dataset.sha = "changed"
    with pytest.raises(RuntimeError):
        dataset.assert_frozen("original")


def test_gold_rejects_bad_quote(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        load_gold(_gold(tmp_path, bad_quote=True))


def test_gold_rejects_duplicate_ids(tmp_path: Path) -> None:
    path = _gold(tmp_path)
    data = json.loads(path.read_text(encoding="utf-8"))
    data["cases"][0]["papers"][1]["paper_id"] = data["cases"][0]["papers"][0]["paper_id"]
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_gold(path)


def test_calibration_perfect() -> None:
    samples = []
    for index in range(24):
        value = 1 + (index % 5)
        samples.append(
            CalibrationSample(
                dimension=DIMENSIONS[index % len(DIMENSIONS)],
                human=float(value),
                judge=float(value),
                human_verdict="accept" if value >= 3 else "repair",
                judge_verdict="accept" if value >= 3 else "repair",
            )
        )
    report = calibrate(samples)
    assert report.passed
    assert report.pearson == 1.0
    assert report.spearman == 1.0
    assert report.mae == 0.0
    assert report.kappa == 1.0


def test_calibration_poor_and_small_sample() -> None:
    samples = [
        CalibrationSample("relevance", float(1 + index % 5), float(5 - index % 5))
        for index in range(24)
    ]
    assert not calibrate(samples).passed
    assert not calibrate(samples[:5]).passed


def test_cohen_kappa() -> None:
    assert cohen_kappa(["accept", "repair"], ["accept", "repair"]) == 1.0
    assert cohen_kappa(["accept", "accept"], ["repair", "repair"]) == 0.0

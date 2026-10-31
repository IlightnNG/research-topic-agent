"""V2 S7/S8: dataset, evaluation and tuning."""

from __future__ import annotations

import json
from pathlib import Path

from lit_agent_v2.evaluation.dataset import EvalDataset, load_dataset
from lit_agent_v2.evaluation.runner import TuneConfig, Tuner
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database

TOPICS = [
    ("tool", "Function calling routes external APIs. Tool routing lowers latency."),
    ("retrieval", "Dense retrievers rank passages. Rerankers sharpen recall."),
    ("planning", "Hierarchical planners decompose tasks. Search budgets prune branches."),
    ("memory", "Episodic buffers store context. Memory lookup persists across turns."),
    ("eval", "Rubric judges score outputs. Annotators calibrate agreement."),
]


def _corpus(root: Path) -> tuple[Path, list[list[str]]]:
    (root / "fulltext").mkdir(parents=True)
    groups: list[list[str]] = []
    with (root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for group, (_topic, text) in enumerate(TOPICS):
            ids: list[str] = []
            for index in range(4):
                pid = f"P{group}{index}"
                ids.append(pid)
                (root / "fulltext" / f"{pid}.txt").write_text(text, encoding="utf-8")
                handle.write(
                    json.dumps({"paper_id": pid, "title": pid, "abstract": text}) + "\n"
                )
            groups.append(ids)
    return root, groups


def _dataset(tmp_path: Path) -> tuple[EvalDataset, Path]:
    root = tmp_path / "eval"
    corpus = root / "corpus"
    _corpus(corpus)
    path = root / "dataset.json"
    path.write_text(
        json.dumps(
            {
                "name": "fixture",
                "version": "1",
                "cases": [
                    {
                        "name": "agents",
                        "topic_id": "agents",
                        "corpus_root": str(corpus),
                        "limit": 20,
                        "focus_hint": "agents",
                        "gold_directions": [
                            [f"P{group}{index}" for index in range(4)]
                            for group in range(5)
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return load_dataset(path), path


def test_dataset_freeze(tmp_path: Path) -> None:
    dataset, path = _dataset(tmp_path)
    assert dataset.sha
    dataset.assert_frozen(dataset.sha)
    changed = EvalDataset.load(path)
    changed.sha = "bad"
    try:
        changed.assert_frozen(dataset.sha)
    except RuntimeError:
        pass
    else:
        raise AssertionError("freeze check did not fail")


def test_direction_f1_and_tuner(tmp_path: Path) -> None:
    dataset, _path = _dataset(tmp_path)
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    tuner = Tuner(db, ArtifactStore(tmp_path / "artifacts"), dataset)
    result = tuner.evaluate(TuneConfig(threshold=0.35, min_size=2))
    assert result.score > 0
    assert "directions.f1" in result.metrics
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM experiments").fetchone()[0] == 1

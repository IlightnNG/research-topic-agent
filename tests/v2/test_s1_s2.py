"""V2 S1/S2 greenfield tests. No legacy imports."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from lit_agent_v2.contracts import NodeSpec, RunRequest, WorkflowDefinition
from lit_agent_v2.contracts.report import Paper
from lit_agent_v2.domains.report.evidence import EvidenceService
from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.domains.report.source import SourceService
from lit_agent_v2.metrics.gates import MetricGateError, assert_metric
from lit_agent_v2.metrics.store import MetricStore
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database


def _db(tmp_path: Path) -> Database:
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    return db


def _workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        name="fake",
        version="1",
        nodes=(
            NodeSpec(id="a", kind="deterministic", output_key="a", postconditions=("value",)),
            NodeSpec(
                id="b",
                kind="deterministic",
                input_keys=("a",),
                output_key="b",
                postconditions=("sum",),
            ),
        ),
    )


def test_s1_workflow_and_resume(tmp_path: Path) -> None:
    db = _db(tmp_path)
    shell = RunShell(db, ArtifactStore(tmp_path / "artifacts"))
    run_id = shell.prepare(RunRequest(topic_id="t1"))
    outputs = shell.run(
        run_id,
        _workflow(),
        handlers={
            "a": lambda _inputs: {"value": 1},
            "b": lambda inputs: {"sum": inputs["a"]["value"] + 1},
        },
    )
    assert outputs["b"]["sum"] == 2
    with db.connect() as conn:
        assert conn.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()[0] == "succeeded"
        assert conn.execute("SELECT COUNT(*) FROM run_nodes").fetchone()[0] == 2

    resumed = shell.run(
        run_id,
        _workflow(),
        handlers={},
        resume=True,
    )
    assert resumed["b"]["sum"] == 2


def test_s1_metric_gate() -> None:
    assert_metric("search.coverage", 0.9, sample_size=90)
    with pytest.raises(MetricGateError):
        assert_metric("search.coverage", 0.5, sample_size=50)
    with pytest.raises(MetricGateError):
        assert_metric("claim.purity", None, sample_size=10)


@pytest.mark.parametrize("count", [20, 50])
def test_s2_source_and_evidence(tmp_path: Path, count: int) -> None:
    corpus_root = tmp_path / "corpus"
    corpus_root.mkdir()
    fulltext_dir = corpus_root / "fulltext"
    fulltext_dir.mkdir()
    papers: list[Paper] = []
    for index in range(count):
        paper = Paper(
            paper_id=f"P{index:03d}",
            title=f"Tool use in agents {index}",
            abstract=f"Tool use improves task success in study {index}.",
            authors=[f"Author {index}"],
            venue="ACL",
            year=2025,
        )
        papers.append(paper)
        if index % 2 == 0:
            (fulltext_dir / f"{paper.paper_id}.txt").write_text(
                f"Tool use improves task success in study {index}. "
                f"Agents use tools to solve problems in benchmark {index}.",
                encoding="utf-8",
            )
    with (corpus_root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for paper in papers:
            handle.write(json.dumps(paper.__dict__) + "\n")

    db = _db(tmp_path)
    metrics = MetricStore(db)
    source = SourceService(metrics).select(
        topic_id="t1", query="tool use", papers=LocalCorpus(corpus_root).papers(), limit=count, run_id="r1"
    )
    assert len(source.papers) == count
    evidence = EvidenceService(metrics).build(source, run_id="r1")
    assert evidence.with_claims == count
    assert evidence.quote_verbatim_rate == 1.0
    assert evidence.claim_purity == 1.0
    assert evidence.fulltext_ratio == 0.5
    assert {point["metric_id"] for point in metrics.points("r1")} >= {
        "search.coverage",
        "card.quote_verbatim_rate",
        "claim.purity",
    }


def test_v2_does_not_import_legacy() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2"
    for path in root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert not node.module.startswith("lit_agent."), f"{path}: {node.module}"
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("lit_agent."), f"{path}: {alias.name}"

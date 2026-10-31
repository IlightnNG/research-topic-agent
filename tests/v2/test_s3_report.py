"""V2 S3: full report workflow, persistence and quality gates."""

from __future__ import annotations

import json
from pathlib import Path

from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.domains.report.workflow import ReportWorkflow
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database

TOPICS = [
    ("tool use", "Function calling routes external APIs. Tool routing lowers latency."),
    ("retrieval", "Dense retrievers rank passages. Rerankers sharpen recall."),
    ("planning", "Hierarchical planners decompose tasks. Search budgets prune branches."),
    ("memory", "Episodic buffers store context. Memory lookup persists across turns."),
    ("evaluation", "Rubric judges score outputs. Annotators calibrate agreement."),
]


def _fixture(tmp_path: Path, *, per_group: int = 10) -> Path:
    root = tmp_path / "corpus"
    root.mkdir()
    full = root / "fulltext"
    full.mkdir()
    with (root / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for group, (topic, vocabulary) in enumerate(TOPICS):
            for index in range(per_group):
                pid = f"P{group}{index:02d}"
                text = vocabulary
                (full / f"{pid}.txt").write_text(text, encoding="utf-8")
                handle.write(
                    json.dumps(
                        {
                            "paper_id": pid,
                            "title": f"{topic.title()} study {index}",
                            "abstract": text,
                            "source": "fixture",
                        }
                    )
                    + "\n"
                )
    return root


def test_s3_full_report_50(tmp_path: Path) -> None:
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    shell = RunShell(db, ArtifactStore(tmp_path / "artifacts"))
    outcome = ReportWorkflow(shell, LocalCorpus(_fixture(tmp_path))).run(
        RunRequest(topic_id="agents", limit=50, focus_hint="agents")
    )

    assert outcome.report_id
    assert len(outcome.mapping.directions) >= 5
    assert outcome.evidence.with_claims == 50
    assert outcome.draft.word_count >= 1500
    assert any(section.kind == "comparison" and "|" in section.body for section in outcome.draft.sections)

    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM report_sections").fetchone()[0] >= 5
        assert conn.execute("SELECT COUNT(*) FROM claims").fetchone()[0] > 0
        assert conn.execute("SELECT state FROM runs").fetchone()[0] == "succeeded"

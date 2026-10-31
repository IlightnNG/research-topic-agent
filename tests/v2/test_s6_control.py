"""V2 S6 control and resume."""

from __future__ import annotations

from pathlib import Path

from lit_agent_v2.contracts import NodeSpec, RunRequest, WorkflowDefinition
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database


def test_pause_abort_state(tmp_path: Path) -> None:
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    shell = RunShell(db, ArtifactStore(tmp_path / "artifacts"))
    run_id = shell.prepare(RunRequest(topic_id="t"))
    shell.pause(run_id)
    assert shell._state(run_id) == "paused"
    shell.resume(run_id)
    assert shell._state(run_id) == "running"
    shell.abort(run_id)
    assert shell._state(run_id) == "aborted"


def test_node_boundary_pause_then_resume(tmp_path: Path) -> None:
    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    shell = RunShell(db, ArtifactStore(tmp_path / "artifacts"))
    run_id = shell.prepare(RunRequest(topic_id="t"))
    definition = WorkflowDefinition(
        name="c",
        version="1",
        nodes=(
            NodeSpec(id="a", kind="deterministic", output_key="a", postconditions=("v",)),
            NodeSpec(
                id="b", kind="deterministic", input_keys=("a",), output_key="b", postconditions=("v",)
            ),
        ),
    )
    calls: list[str] = []

    def a(_inputs):
        calls.append("a")
        shell.pause(run_id)
        return {"v": 1}

    def b(inputs):
        calls.append("b")
        return {"v": inputs["a"]["v"] + 1}

    first = shell.run(run_id, definition, handlers={"a": a, "b": b})
    assert first["a"]["v"] == 1
    assert shell._state(run_id) == "paused"
    shell.resume(run_id)
    outputs = shell.run(run_id, definition, handlers={"a": a, "b": b}, resume=True)
    assert outputs["b"]["v"] == 2
    assert calls == ["a", "b"]


def test_report_pause_and_resume_from_committed_node(tmp_path: Path) -> None:
    from lit_agent_v2.composition import build_report_workflow
    from lit_agent_v2.contracts import RunRequest
    from lit_agent_v2.domains.report.ingest import LocalCorpus
    from lit_agent_v2.domains.report.source import LocalCorpusSource, SourceService

    corpus = tmp_path / "corpus"
    (corpus / "fulltext").mkdir(parents=True)
    with (corpus / "papers.jsonl").open("w", encoding="utf-8") as handle:
        for index in range(10):
            text = f"Tool use improves agent success in study {index}."
            (corpus / "fulltext" / f"P{index}.txt").write_text(text, encoding="utf-8")
            handle.write(__import__("json").dumps({"paper_id": f"P{index}", "title": "tool", "abstract": text}) + "\n")

    db = Database(tmp_path / "v2.sqlite")
    db.migrate()
    shell = RunShell(db, ArtifactStore(tmp_path / "artifacts"))
    holder: dict[str, str] = {}

    class PausingSource(LocalCorpusSource):
        def __init__(self, corpus):  # noqa: ANN001
            super().__init__(corpus, SourceService())

        def select(self, **kwargs):  # noqa: ANN003
            artifact = super().select(**kwargs)
            shell.pause(holder["run_id"])
            return artifact

    request = RunRequest(topic_id="agents", limit=10, focus_hint="tool use")
    run_id = shell.prepare(request)
    holder["run_id"] = run_id
    workflow = build_report_workflow(
        shell, LocalCorpus(corpus), source=PausingSource(LocalCorpus(corpus))
    )
    import pytest

    with pytest.raises(RuntimeError):
        workflow.run(request, run_id=run_id)
    assert shell._state(run_id) == "paused"
    shell.resume(run_id)
    outcome = workflow.run(request, run_id=run_id, resume=True)
    assert outcome.report_id
    with db.connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM reports").fetchone()[0] == 1

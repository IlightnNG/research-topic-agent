"""Report workflow v2 shape and deterministic tool-chain tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lit_agent_v2.interface.runs import PlatformRunService
from lit_agent_v2.storage.db import Database
from lit_agent_v2.tools.packs.report_v2 import (
    assemble_sections,
    check_report_quality,
    finalize_report,
    plan_from_evidence,
    write_next_section,
    write_one_section,
    write_report,
)
from lit_agent_v2.workflow.node.file_store import JsonNodeStore
from lit_agent_v2.workflow.report_v2 import (
    REPORT_V2_NODES,
    build_report_v2_workflow,
    report_v2_toolsets,
)
from lit_agent_v2.workflow.report_v2_runtime import build_report_v2_runtime


def test_workflow_has_five_multi_tool_nodes() -> None:
    definition = build_report_v2_workflow()
    assert [node.id for node in definition.nodes] == list(REPORT_V2_NODES)
    for node in definition.nodes:
        assert len(node.tools) >= 3
        assert node.toolset == node.id
        assert any(name in node.tools for name in ("context.inspect", "context.compact", "plan.update"))


def test_runtime_exposes_node_toolsets() -> None:
    runtime = build_report_v2_runtime(None)
    for node_id in REPORT_V2_NODES:
        names = {spec.name for spec in runtime.specs(node_id)}
        assert names == set(report_v2_toolsets()[node_id])


def test_report_v2_tool_chain(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    papers = []
    for index in range(8):
        paper_id = f"P{index}"
        abstract = (
            f"Tool agents solve tasks with explicit calls in environment {index}. "
            f"Evidence shows recovery improves success for task {index}. "
            f"The evaluation separates correctness from recoverability in run {index}."
        )
        papers.append(
            {"paper_id": paper_id, "title": f"Paper {index}", "abstract": abstract}
        )
    (corpus / "papers.jsonl").write_text(
        "\n".join(json.dumps(paper) for paper in papers), encoding="utf-8"
    )
    out = tmp_path / "out"
    from lit_agent_v2.tools.packs.demo import collect_source, extract_evidence

    source = collect_source(str(corpus), str(out), limit=100)
    assert source["papers"] == 8
    evidence = extract_evidence(source["source_path"], str(out))
    assert evidence["claims"] > 0
    plan = plan_from_evidence(evidence["evidence_path"], str(out))
    assert plan["sections"] >= 3
    draft = write_report(
        plan["plan_path"],
        evidence["evidence_path"],
        str(out),
        llm=None,
    )
    assert draft["sections"] >= 3
    assert draft["citation_coverage"] > 0
    evidence_doc = json.loads(Path(evidence["evidence_path"]).read_text(encoding="utf-8"))
    draft_doc = json.loads(Path(draft["draft_path"]).read_text(encoding="utf-8"))
    quality = check_report_quality(draft_doc, evidence_doc)
    assert quality["metrics"]["sections"] == draft["sections"]
    assert quality["metrics"]["section_metrics"]
    assert quality["metrics"]["uncovered_claims"] >= 0
    with pytest.raises(ValueError, match="E_REPORT_QUALITY"):
        finalize_report(
            draft["draft_path"],
            evidence["evidence_path"],
            str(out),
            strict_quality=True,
        )
    final = finalize_report(
        draft["draft_path"], evidence["evidence_path"], str(out)
    )
    assert final["papers"] == 8
    assert final["sections"] >= 3
    assert final["citation_coverage"] > 0
    assert Path(final["report_path"]).exists()
    assert Path(final["path"]).exists()


def test_section_retry_and_checkpoint(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    from lit_agent_v2.tools.packs import report_v2

    out = tmp_path / "out"
    out.mkdir()
    evidence = {
        "claims": [
            {
                "claim_id": "C1",
                "paper_id": "P1",
                "quote": "Evidence shows recovery improves success.",
                "text": "Evidence shows recovery improves success.",
            }
        ],
        "papers": [{"paper_id": "P1", "title": "Paper"}],
    }
    plan = {
        "sections": [
            {
                "section_id": "s1",
                "kind": "paper_analysis",
                "title": "Paper",
                "paper_ids": ["P1"],
            }
        ]
    }
    evidence_path = out / "evidence.json"
    plan_path = out / "plan.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    class LLM:
        def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
            return {"body": "Evidence shows recovery improves success [C1]."}, None

    original = report_v2.write_section
    calls = {"n": 0}

    def flaky(section, claims, llm, **kwargs):  # noqa: ANN001, ARG002
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "problems": ["forced"], "section": {"body": ""}}
        return original(section, claims, llm, **kwargs)

    monkeypatch.setattr(report_v2, "write_section", flaky)
    result = write_one_section(
        str(plan_path), "s1", str(evidence_path), str(out), llm=LLM()
    )
    assert result["attempts"] == 2
    assert result["ok"] is True
    assert result["fallback"] is False
    assert Path(result["section_path"]).exists()

    store = JsonNodeStore(tmp_path / "nodes")
    from lit_agent_v2.contracts.verdict import Verdict

    store.commit("run", "source.collect", {"ok": True}, Verdict(True))
    assert store.state("run", "source.collect") == "committed"
    assert store.load_output("run", "source.collect") == {"ok": True}


def test_api_workflow_selects_report_v2(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    monkeypatch.setenv("LIT_V2_WORKFLOW", "report-v2")
    db = Database(tmp_path / "api.sqlite")
    db.migrate()
    service = PlatformRunService(db, corpus_root=tmp_path)
    workflow = service._workflow({"id": "topic"}, None, "en")
    assert [node.id for node in workflow.nodes] == list(REPORT_V2_NODES)


def test_no_demo_orchestrator_in_interface() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2" / "interface"
    assert root.exists()
    for path in root.glob("*.py"):
        assert "DemoOrchestrator" not in path.read_text(encoding="utf-8"), path


def test_section_cursor_loop(tmp_path: Path) -> None:
    out = tmp_path / "out"
    out.mkdir()
    evidence = {
        "claims": [
            {"claim_id": "C1", "paper_id": "P1", "quote": "Evidence one.", "text": "Evidence one."},
            {"claim_id": "C2", "paper_id": "P2", "quote": "Evidence two.", "text": "Evidence two."},
        ],
        "papers": [{"paper_id": "P1"}, {"paper_id": "P2"}],
    }
    plan = {
        "sections": [
            {"section_id": "s1", "kind": "paper_analysis", "title": "One", "paper_ids": ["P1"]},
            {"section_id": "s2", "kind": "paper_analysis", "title": "Two", "paper_ids": ["P2"]},
        ]
    }
    ep = out / "evidence.json"
    pp = out / "plan.json"
    ep.write_text(json.dumps(evidence), encoding="utf-8")
    pp.write_text(json.dumps(plan), encoding="utf-8")

    first = write_next_section(str(pp), str(ep), str(out), llm=None)
    assert first["written"] == 1
    assert first["next_section"] == "s2"
    second = write_next_section(str(pp), str(ep), str(out), llm=None)
    assert second["written"] == 2
    assert second["done"] is True
    draft = assemble_sections(str(pp), str(ep), str(out))
    assert draft["sections"] == 2
    assert draft["citation_coverage"] == 1.0

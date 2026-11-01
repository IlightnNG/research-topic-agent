"""Phase 4.1.6: one report node, end-to-end with a local corpus."""

from __future__ import annotations

import json
from pathlib import Path

from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.kernel.node.loop import Kernel
from lit_agent_v2.tools.packs.claims import build_claim_tools
from lit_agent_v2.tools.packs.corpus import build_corpus_tools
from lit_agent_v2.tools.packs.report import build_report_tools
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.node.definition import build_report_demo_workflow
from lit_agent_v2.workflow.node.runner import WorkflowRunner


class ScriptLLM:
    def __init__(self, actions: list[dict]) -> None:
        self.actions = actions
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        action = self.actions[min(self.calls, len(self.actions) - 1)]
        self.calls += 1
        return action, None


class SectionLLM:
    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        return {"body": "Evidence summary [C1]. Second finding [C2]."}, None


class Store:
    def __init__(self) -> None:
        self.committed: dict[str, dict] = {}

    def state(self, run_id: str, node_id: str) -> str | None:
        return None

    def load_output(self, run_id: str, node_id: str) -> dict | None:
        return None

    def commit(self, run_id: str, node_id: str, output: dict, verdict: Verdict) -> None:
        self.committed[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        pass


def test_report_node_end_to_end(tmp_path: Path) -> None:
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    papers = [
        {
            "paper_id": "P1",
            "title": "Tool Agents",
            "abstract": "Tool use improves agent success on benchmark tasks.",
        },
        {
            "paper_id": "P2",
            "title": "Citation Evaluation",
            "abstract": "Citation coverage measures unsupported claims in summaries.",
        },
    ]
    (corpus / "papers.jsonl").write_text(
        "\n".join(json.dumps(paper) for paper in papers) + "\n", encoding="utf-8"
    )
    claims = [
        {"claim_id": "C1", "paper_id": "P1", "quote": "Tool use improves agent success"},
        {"claim_id": "C2", "paper_id": "P2", "quote": "Citation coverage measures unsupported claims"},
    ]
    sections = [
        {"section_id": "overview", "kind": "overview", "title": "At a Glance"},
        {
            "section_id": "paper_analysis_001",
            "kind": "paper_analysis",
            "title": "Papers 1-2",
            "paper_ids": ["P1", "P2"],
        },
        {"section_id": "synthesis", "kind": "synthesis", "title": "Synthesis"},
        {"section_id": "paper_index", "kind": "paper_index", "title": "Paper Index"},
    ]
    actions = [
        {"action": "tool", "calls": [{"id": "c1", "name": "corpus.papers", "args": {"root": str(corpus)}}]},
        {
            "action": "tool",
            "calls": [
                {
                    "id": "c2",
                    "name": "claims.extract",
                    "args": {"paper_id": "P1", "text": papers[0]["abstract"]},
                },
                {
                    "id": "c3",
                    "name": "claims.extract",
                    "args": {"paper_id": "P2", "text": papers[1]["abstract"]},
                },
            ],
        },
        {"action": "tool", "calls": [{"id": "c4", "name": "report.plan", "args": {"papers": papers}}]},
        {
            "action": "tool",
            "calls": [
                {
                    "id": f"w{i}",
                    "name": "report.write_section",
                    "args": {"section": section, "claims": claims},
                }
                for i, section in enumerate(sections)
            ],
        },
        {
            "action": "tool",
            "calls": [
                {
                    "id": "a1",
                    "name": "report.assemble",
                    "args": {"title": "T", "sections": [{"body": "Evidence [C1] [C2]."}]},
                }
            ],
        },
        {
            "action": "tool",
            "calls": [
                {
                    "id": "p1",
                    "name": "report.persist",
                    "args": {
                        "root": str(tmp_path / "out"),
                        "title": "T",
                        "content_md": "Evidence [C1] [C2].",
                        "claims": claims,
                    },
                }
            ],
        },
        {
            "action": "final",
            "outputs": {
                "title": "T",
                "content_md": "Evidence [C1] [C2].",
                "claims": claims,
                "path": str(tmp_path / "out" / "report.json"),
            },
        },
    ]
    registry = ToolRegistry(
        build_corpus_tools() + build_claim_tools() + build_report_tools(SectionLLM())
    )
    kernel = Kernel(ScriptLLM(actions), registry)
    store = Store()
    workflow = build_report_demo_workflow()
    outputs = WorkflowRunner(
        kernel=kernel,
        verifier=Verifier(),
        store=store,
    ).run(workflow, run_id="r1", inputs={"request": {"root": str(corpus)}})
    assert "report.generate" in store.committed
    assert outputs["report.generate"]["title"] == "T"
    assert Path(outputs["report.generate"]["path"]).exists()
    assert (tmp_path / "out" / "report.md").exists()

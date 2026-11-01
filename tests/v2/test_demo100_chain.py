"""Full 4-Node 100-paper demo chain, deterministic tool execution."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.kernel.node.loop import Kernel
from lit_agent_v2.tools.packs.demo import build_demo_tools
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.node.definition import build_demo100_workflow
from lit_agent_v2.workflow.node.runner import WorkflowRunner

ROOT = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents")


class ScriptedLLM:
    def __init__(self, root: Path, out_dir: Path) -> None:
        self.root = root
        self.out_dir = out_dir
        self.calls: dict[str, int] = {}

    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        system = messages[0]["content"]
        node_id = next(
            line.split("Node: ", 1)[1]
            for line in system.splitlines()
            if line.startswith("Node: ")
        )
        count = self.calls.get(node_id, 0)
        self.calls[node_id] = count + 1
        source_path = str(self.out_dir / "source.json")
        evidence_path = str(self.out_dir / "evidence.json")
        report_path = str(self.out_dir / "report.json")
        if node_id == "source.collect":
            if count == 0:
                return {
                    "action": "tool",
                    "calls": [
                        {
                            "id": "s1",
                            "name": "demo.source",
                            "args": {"root": str(self.root), "out_dir": str(self.out_dir)},
                        }
                    ],
                }, None
            return {
                "action": "final",
                "outputs": {
                    "source_path": source_path,
                    "papers": 100,
                    "fulltext": 0,
                    "fulltext_ratio": 0.0,
                    "state": "degraded",
                },
            }, None
        if node_id == "evidence.extract":
            if count == 0:
                return {
                    "action": "tool",
                    "calls": [
                        {
                            "id": "e1",
                            "name": "demo.evidence",
                            "args": {"source_path": source_path, "out_dir": str(self.out_dir)},
                        }
                    ],
                }, None
            return {
                "action": "final",
                "outputs": {"evidence_path": evidence_path, "papers": 100, "claims": 100},
            }, None
        if node_id == "report.generate":
            if count == 0:
                return {
                    "action": "tool",
                    "calls": [
                        {
                            "id": "r1",
                            "name": "demo.report",
                            "args": {
                                "source_path": source_path,
                                "evidence_path": evidence_path,
                                "out_dir": str(self.out_dir),
                                "language": "en",
                            },
                        }
                    ],
                }, None
            return {
                "action": "final",
                "outputs": {
                    "report_path": report_path,
                    "papers": 100,
                    "claims": 100,
                    "sections": 13,
                    "word_count": 1000,
                    "state": "degraded",
                },
            }, None
        if count == 0:
            return {
                "action": "tool",
                "calls": [
                    {
                        "id": "f1",
                        "name": "demo.finalize",
                        "args": {"report_path": report_path, "out_dir": str(self.out_dir)},
                    }
                ],
            }, None
        return {
            "action": "final",
            "outputs": {
                "report_path": report_path,
                "content_sha": "x",
                "papers": 100,
                "claims": 100,
                "state": "degraded",
            },
        }, None


class Store:
    def __init__(self) -> None:
        self.outputs: dict[str, dict] = {}

    def state(self, run_id: str, node_id: str) -> str | None:
        return None

    def load_output(self, run_id: str, node_id: str) -> dict | None:
        return None

    def commit(self, run_id: str, node_id: str, output: dict, verdict: Verdict) -> None:
        self.outputs[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        pass


def test_demo100_full_chain(tmp_path: Path) -> None:
    if not (ROOT / "papers.jsonl").exists():
        pytest.skip("local 100-paper corpus is not available")
    out_dir = tmp_path / "v2-demo"
    out_dir.mkdir()
    tools = ToolRegistry(build_demo_tools())
    llm = ScriptedLLM(ROOT, out_dir)
    kernel = Kernel(llm, tools)
    store = Store()
    workflow = build_demo100_workflow()
    outputs = WorkflowRunner(kernel=kernel, verifier=Verifier(), store=store).run(
        workflow,
        run_id="demo100-test",
        inputs={"request": {"root": str(ROOT), "out_dir": str(out_dir), "language": "en"}},
    )
    assert outputs["source.collect"]["papers"] == 100
    assert outputs["evidence.extract"]["claims"] >= 100
    report = json.loads((out_dir / "report.json").read_text(encoding="utf-8"))
    assert report["papers"] == 100
    assert len(report["claims"]) >= 100
    assert len(report["sections"]) >= 5
    assert report["state"] == "degraded"
    final = json.loads((out_dir / "final.json").read_text(encoding="utf-8"))
    assert final["papers"] == 100

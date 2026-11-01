"""Run the full 100-paper demo chain against the local corpus.

Usage (from repository root):

    . .\\scripts\\env.ps1
    uv run python scripts/demo100.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config
from lit_agent_v2.kernel.node.loop import Kernel
from lit_agent_v2.tools.packs.demo import build_demo_tools
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.node.definition import build_demo100_workflow
from lit_agent_v2.workflow.node.runner import WorkflowRunner

DEFAULT_CORPUS = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents")
DEFAULT_OUT = Path(r"D:\lit-agent-store\v2-demo")


class MemoryStore:
    def __init__(self) -> None:
        self.outputs: dict[str, dict[str, Any]] = {}

    def state(self, run_id: str, node_id: str) -> str | None:
        return None

    def load_output(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        return None

    def commit(
        self, run_id: str, node_id: str, output: dict[str, Any], verdict: Verdict
    ) -> None:
        self.outputs[node_id] = output

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        self.outputs[node_id] = {"degraded": True, "reason": reason}


class ConsoleEvents:
    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> None:
        if event_type in {"node.started", "node.committed", "node.failed", "run.finished"}:
            print(f"[{event_type}] {node_id or ''} {payload}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"corpus={args.corpus}")
    print(f"out={args.out}")
    workflow = build_demo100_workflow()
    store = MemoryStore()
    kernel = Kernel(
        DeepSeekChatClient(load_llm_config()),
        ToolRegistry(build_demo_tools()),
        events=ConsoleEvents(),
        max_retries=1,
    )
    runner = WorkflowRunner(
        kernel=kernel,
        verifier=Verifier(),
        store=store,
        events=ConsoleEvents(),
    )
    outputs = runner.run(
        workflow,
        run_id="demo100-cli",
        inputs={
            "request": {
                "root": str(args.corpus),
                "out_dir": str(args.out),
                "language": "en",
            }
        },
    )
    print(json.dumps(outputs, ensure_ascii=False, indent=2))
    report_path = Path(str(outputs["report.generate"]["report_path"]))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    claims = list(report.get("claims") or [])
    sections = list(report.get("sections") or [])
    quotes = {
        " ".join(str(claim.get("quote", "")).split()).lower()
        for claim in claims
    }
    duplicate_rate = 1 - len(quotes) / len(claims) if claims else 0.0
    metrics = {
        "papers": report.get("papers"),
        "claims": len(claims),
        "sections": len(sections),
        "words": report.get("word_count"),
        "state": report.get("state"),
        "duplicate_rate": round(duplicate_rate, 3),
    }
    print("REPORT", metrics)
    problems = []
    if int(report.get("papers") or 0) < 100:
        problems.append("papers < 100")
    if len(claims) < 100:
        problems.append("claims < 100")
    if len(sections) < 5:
        problems.append("sections < 5")
    if duplicate_rate > 0.1:
        problems.append("duplicate claim rate > 0.1")
    if report.get("state") not in {"complete", "degraded"}:
        problems.append("invalid report state")
    if problems:
        print("ACCEPTANCE FAIL", problems)
        return 1
    print("ACCEPTANCE PASS")
    print("final", args.out / "final.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Command line entrypoint for the platform demo."""

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

__all__ = ["main"]

DEFAULT_CORPUS = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents")
DEFAULT_OUT = Path(r"D:\lit-agent-store\v2-demo")


class _MemoryStore:
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


class _Events:
    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> None:
        if event_type in {"node.started", "node.committed", "node.failed"}:
            print(f"[{event_type}] {node_id or ''}")


def main() -> int:
    parser = argparse.ArgumentParser(prog="lit-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    demo = sub.add_parser("demo100", help="run the 100-paper full Node chain")
    demo.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    demo.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    kernel = Kernel(
        DeepSeekChatClient(load_llm_config()),
        ToolRegistry(build_demo_tools()),
        events=_Events(),
    )
    outputs = WorkflowRunner(
        kernel=kernel,
        verifier=Verifier(),
        store=_MemoryStore(),
        events=_Events(),
    ).run(
        build_demo100_workflow(),
        run_id="demo100-cli",
        inputs={
            "request": {
                "root": str(args.corpus),
                "out_dir": str(args.out),
                "language": "en",
            }
        },
    )
    report_path = Path(str(outputs["report.generate"]["report_path"]))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "report_path": str(report_path),
                "papers": report.get("papers"),
                "claims": len(report.get("claims") or []),
                "sections": len(report.get("sections") or []),
                "words": report.get("word_count"),
                "state": report.get("state"),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

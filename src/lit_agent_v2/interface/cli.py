"""Command line entrypoint for the platform demo."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.verdict import Verdict
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore
from lit_agent_v2.kernel.agent.node import KernelNodeAdapter
from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.node.file_store import JsonNodeStore
from lit_agent_v2.workflow.node.runner import WorkflowRunner
from lit_agent_v2.workflow.report_v2 import build_report_v2_workflow
from lit_agent_v2.workflow.report_v2_runtime import build_report_v2_runtime

__all__ = ["main"]

DEFAULT_CORPUS = Path(r"D:\lit-agent-store\v2-eval\gold\corpora\agents-fulltext")
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
    v2 = sub.add_parser("report-v2", help="run the 5-node report workflow on the generic AgentKernel")
    v2.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    v2.add_argument("--out", type=Path, default=DEFAULT_OUT)
    v2.add_argument("--language", default="en")
    v2.add_argument("--limit", type=int, default=20)
    v2.add_argument("--source-mode", choices=("local", "online", "auto"), default="local")
    v2.add_argument("--query", default=None)
    v2.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    args.out.mkdir(parents=True, exist_ok=True)
    llm = DeepSeekChatClient(load_llm_config())
    if args.command == "report-v2":
        runtime = build_report_v2_runtime(llm)
        adapter = KernelNodeAdapter(
            llm,
            runtime,
            workspace=args.out,
            checkpoints=FileCheckpointStore(args.out / "checkpoints"),
        )
        outputs = WorkflowRunner(
            kernel=adapter,
            verifier=Verifier(),
            store=JsonNodeStore(args.out / "nodes"),
            events=_Events(),
        ).run(
            build_report_v2_workflow(),
            run_id="report-v2-cli",
            inputs={
                "request": {
                    "root": str(args.corpus),
                    "out_dir": str(args.out),
                    "language": args.language,
                    "limit": args.limit,
                    "source_mode": args.source_mode,
                    "query": args.query,
                }
            },
            resume=args.resume,
        )
        final = outputs["report.audit_finalize"]
        print(
            json.dumps(
                {
                    "report_path": final.get("report_path"),
                    "papers": final.get("papers"),
                    "claims": final.get("claims"),
                    "sections": final.get("sections"),
                    "words": final.get("word_count"),
                    "state": final.get("state"),
                    "citation_coverage": final.get("citation_coverage"),
                },
                ensure_ascii=False,
            )
        )
        return 0
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

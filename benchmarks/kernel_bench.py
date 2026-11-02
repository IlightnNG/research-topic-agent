"""Deterministic Kernel benchmark harness.

This exercises the control plane and general tools without calling a model.
It is a regression/performance harness, not a quality benchmark.
"""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {"type": "object", "required": ["ok"]}


class ScriptedLLM:
    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.index = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action, None


def call(call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"action": "tool", "calls": [{"id": call_id, "name": name, "args": args}]}


def final() -> dict[str, Any]:
    return {"action": "final", "outputs": {"ok": True}}


@dataclass(frozen=True)
class Case:
    name: str
    actions: tuple[dict[str, Any], ...]
    seed_history: int = 0


def cases() -> list[Case]:
    base = [
        Case(
            "plan-artifact",
            (
                call("p", "plan.create", {"goal": "bench", "steps": ["one", "two"]}),
                call("a", "artifact.put", {"name": "out.txt", "content": "ok"}),
                final(),
            ),
        ),
        Case(
            "fs-roundtrip",
            (
                call("w", "fs.write", {"path": "x.txt", "content": "x"}),
                call("r", "fs.read", {"path": "x.txt"}),
                final(),
            ),
        ),
        Case(
            "memory",
            (
                call("w", "memory.write", {"key": "k", "value": {"v": 1}}),
                call("s", "memory.search", {"query": "k"}),
                final(),
            ),
        ),
        Case(
            "artifact-verify",
            (
                call("a", "artifact.put", {"name": "x.json", "content": '{"ok": true}'}),
                call("v", "verify.code", {"path": "artifacts", "required_keys": []}),
                final(),
            ),
        ),
        Case(
            "context",
            (
                call("c", "context.compact", {"keep_recent": 2}),
                call("i", "context.inspect", {}),
                final(),
            ),
            seed_history=12,
        ),
        Case(
            "multi-tool",
            (
                call("w1", "fs.write", {"path": "a.txt", "content": "a"}),
                call("w2", "fs.write", {"path": "b.txt", "content": "b"}),
                final(),
            ),
        ),
    ]
    return [Case(f"{case.name}-{index}", case.actions, case.seed_history) for index in range(5) for case in base]


def run_case(case: Case, root: Path) -> dict[str, Any]:
    workspace = root / case.name
    state = GeneralState(workspace=workspace)
    state.history.extend(
        [{"role": "tool", "call_id": f"seed{i}", "content": "z" * 500} for i in range(case.seed_history)]
    )
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    started = time.perf_counter()
    result = AgentKernel(ScriptedLLM(list(case.actions)), runtime, state).run(
        KernelTask(
            task_id=case.name,
            goal=case.name,
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=6),
        )
    )
    elapsed = (time.perf_counter() - started) * 1000
    return {
        "case": case.name,
        "success": result.stop_reason == "final",
        "steps": result.steps,
        "tool_calls": result.metrics.get("tool_calls", 0),
        "tool_errors": result.metrics.get("tool_errors", 0),
        "compactions": result.metrics.get("compactions", 0),
        "latency_ms": elapsed,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, default=Path("D:/lit-agent-store/kernel-benchmark.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory() as temp:
        results = [run_case(case, Path(temp)) for case in cases()]
    latencies = sorted(item["latency_ms"] for item in results)
    p95 = latencies[max(0, int(len(latencies) * 0.95) - 1)]
    summary = {
        "cases": len(results),
        "success": sum(1 for item in results if item["success"]),
        "success_rate": sum(1 for item in results if item["success"]) / len(results),
        "tool_errors": sum(item["tool_errors"] for item in results),
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": p95,
        "results": results,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False))
    return 0 if summary["success"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

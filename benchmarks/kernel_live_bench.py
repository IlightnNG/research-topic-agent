"""Real-LLM kernel benchmark: 30 tasks across general tools."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.observability import MemoryEventSink
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config
from lit_agent_v2.storage.db import Database
from lit_agent_v2.storage.kernel_metrics import KernelMetricStore
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


@dataclass(frozen=True)
class Case:
    name: str
    goal: str
    setup: Callable[[Path], None]
    verify: Callable[[GeneralState], bool]


def _write(name: str, text: str) -> Callable[[Path], None]:
    def setup(workspace: Path) -> None:
        (workspace / name).write_text(text, encoding="utf-8")

    return setup


def _test_file(workspace: Path) -> None:
    (workspace / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )


def build_cases() -> list[Case]:
    cases: list[Case] = []
    for index in range(5):
        filename = f"input-{index}.txt"
        cases.append(
            Case(
                name=f"read-{index}",
                goal=(
                    f"You MUST call fs.read on {filename}. "
                    "Then return final JSON with ok=true."
                ),
                setup=_write(filename, f"payload-{index}"),
                verify=lambda state, name=filename: any(
                    item.get("name") == "fs.read" and name in str(item.get("content"))
                    for item in state.history
                ),
            )
        )
        cases.append(
            Case(
                name=f"artifact-{index}",
                goal=(
                    'You MUST call artifact.put with name "result.txt" and content "ok". '
                    "Then return final JSON with ok=true."
                ),
                setup=lambda _workspace: None,
                verify=lambda state: any(
                    "result.txt" in path.name for path in state.artifacts.glob("*")
                ),
            )
        )
        cases.append(
            Case(
                name=f"plan-{index}",
                goal=(
                    'You MUST call plan.create with goal "bench" and steps ["inspect","finish"]. '
                    "Then return final JSON with ok=true."
                ),
                setup=lambda _workspace: None,
                verify=lambda state: bool(state.plans),
            )
        )
        cases.append(
            Case(
                name=f"list-{index}",
                goal="You MUST call fs.list on path '.'. Then return final JSON with ok=true.",
                setup=_write(f"file-{index}.txt", "x"),
                verify=lambda state: any(item.get("name") == "fs.list" for item in state.history),
            )
        )
        cases.append(
            Case(
                name=f"memory-{index}",
                goal=(
                    'You MUST call memory.write with key "done" and value {"index": '
                    f"{index}"
                    '}. Then return final JSON with ok=true.'
                ),
                setup=lambda _workspace: None,
                verify=lambda state: bool(state.memory),
            )
        )
        cases.append(
            Case(
                name=f"test-{index}",
                goal=(
                    "You MUST call test.run with target test_sample.py. "
                    "Then return final JSON with ok=true."
                ),
                setup=_test_file,
                verify=lambda state: any(item.get("name") == "test.run" for item in state.history),
            )
        )
    return cases


def run_case(case: Case, root: Path, llm: DeepSeekChatClient) -> dict[str, Any]:
    workspace = root / case.name
    workspace.mkdir(parents=True, exist_ok=True)
    case.setup(workspace)
    state = GeneralState(workspace=workspace)
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    events = MemoryEventSink()
    started = time.perf_counter()
    result = AgentKernel(llm, runtime, state, events=events).run(
        KernelTask(
            task_id=case.name,
            goal=case.goal,
            inputs={"workspace": str(workspace)},
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=4, max_usd=0.20, max_repair=1),
        )
    )
    latency = (time.perf_counter() - started) * 1000
    schema_ok = result.output.get("ok") is True
    verified = False
    try:
        verified = case.verify(state)
    except Exception:
        verified = False
    success = result.stop_reason == "final" and schema_ok and verified
    return {
        "case": case.name,
        "success": success,
        "schema_ok": schema_ok,
        "verified": verified,
        "stop_reason": result.stop_reason,
        "error_code": result.error_code,
        "steps": result.metrics.get("steps", 0),
        "tool_calls": result.metrics.get("tool_calls", 0),
        "tool_errors": result.metrics.get("tool_errors", 0),
        "repairs": result.metrics.get("repairs", 0),
        "compactions": result.metrics.get("compactions", 0),
        "prompt_tokens": result.usage.get("prompt_tokens", 0),
        "completion_tokens": result.usage.get("completion_tokens", 0),
        "cost_usd": result.cost_usd,
        "latency_ms": latency,
        "result": result,
        "events": events,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--db", type=Path, default=Path("D:/lit-agent-store/kernel-live-metrics.sqlite"))
    parser.add_argument("--out", type=Path, default=Path("D:/lit-agent-store/kernel-live-benchmark.json"))
    args = parser.parse_args()
    db = Database(args.db)
    db.migrate()
    store = KernelMetricStore(db)
    llm = DeepSeekChatClient(load_llm_config())
    cases = build_cases()[: args.limit]
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        for case in cases:
            row = run_case(case, Path(temp), llm)
            result = row.pop("result")
            row.pop("events")
            store.record(
                result,
                task_id=case.name,
                model=llm.config.model,
                schema_ok=row["schema_ok"],
                latency_ms=row["latency_ms"],
                metadata={"verified": row["verified"], "case": case.name},
            )
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "result"}, ensure_ascii=False))
    latencies = sorted(row["latency_ms"] for row in rows)
    summary = {
        "cases": len(rows),
        "success": sum(1 for row in rows if row["success"]),
        "success_rate": sum(1 for row in rows if row["success"]) / len(rows) if rows else 0.0,
        "schema_ok": sum(1 for row in rows if row["schema_ok"]),
        "tool_errors": sum(row["tool_errors"] for row in rows),
        "prompt_tokens": sum(row["prompt_tokens"] for row in rows),
        "completion_tokens": sum(row["completion_tokens"] for row in rows),
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "latency_p50_ms": statistics.median(latencies) if latencies else 0.0,
        "latency_p95_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)] if latencies else 0.0,
        "results": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False))
    return 0 if summary["success"] == summary["cases"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

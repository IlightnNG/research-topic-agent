"""Complex multi-step real-LLM benchmark with optional audit metrics."""

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

from lit_agent_v2.kernel.agent.audit import LLMAuditor
from lit_agent_v2.kernel.agent.loop import AgentKernel
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
    "properties": {"ok": {"type": "boolean"}, "summary": {"type": "string"}},
    "required": ["ok"],
}


@dataclass(frozen=True)
class Case:
    name: str
    goal: str
    setup: Callable[[Path], None]
    verify: Callable[[GeneralState], bool]


def _file(name: str, text: str) -> Callable[[Path], None]:
    def setup(workspace: Path) -> None:
        (workspace / name).write_text(text, encoding="utf-8")

    return setup


def build_cases() -> list[Case]:
    return [
        Case(
            "read-summarize-artifact",
            (
                "You MUST call fs.read on input.txt. Then call artifact.put with name "
                'summary.txt and a short summary. Finally return {"ok":true,"summary":"..."} .'
            ),
            _file("input.txt", "alpha beta gamma"),
            lambda state: any(path.name.endswith("summary.txt") for path in state.artifacts.glob("*")),
        ),
        Case(
            "plan-write-verify",
            (
                'You MUST call plan.create with goal "deliver" and steps ["write","verify"]. '
                'Then fs.write path out.txt content "done". Then verify.code path out.txt. '
                'Finally return {"ok":true,"summary":"..."} .'
            ),
            lambda _workspace: None,
            lambda state: bool(state.plans) and any(item.get("name") == "verify.code" for item in state.history),
        ),
        Case(
            "multi-read-artifact",
            (
                "You MUST call fs.read on a.txt and b.txt. Then artifact.put with name "
                "combined.txt containing both values. Finally return ok=true."
            ),
            lambda workspace: (
                (workspace / "a.txt").write_text("A", encoding="utf-8"),
                (workspace / "b.txt").write_text("B", encoding="utf-8"),
            ),
            lambda state: sum(1 for item in state.history if item.get("name") == "fs.read") >= 2,
        ),
        Case(
            "memory-plan",
            (
                "You MUST call memory.write key finding value {note:'done'}. Then plan.create "
                'goal "memory" steps ["write","finish"]. Finally return ok=true.'
            ),
            lambda _workspace: None,
            lambda state: bool(state.memory) and bool(state.plans),
        ),
        Case(
            "write-list",
            (
                "You MUST call fs.write path a.txt content 'a', then fs.write path b.txt content 'b', "
                "then fs.list path '.'. Finally return ok=true."
            ),
            lambda _workspace: None,
            lambda state: sum(1 for item in state.history if item.get("name") == "fs.write") >= 2,
        ),
        Case(
            "plan-complete",
            (
                'You MUST call plan.create goal "steps" steps ["one","two"]. Then plan.complete_step '
                'with the plan id and step_id s1. Then plan.read. Finally return ok=true.'
            ),
            lambda _workspace: None,
            lambda state: bool(state.plans),
        ),
        Case(
            "artifact-verify",
            (
                'You MUST call fs.write path result.json content \'{"ok": true}\'. Then '
                "verify.code path result.json required_keys ['ok']. Finally return ok=true."
            ),
            lambda _workspace: None,
            lambda state: any(item.get("name") == "verify.code" for item in state.history),
        ),
        Case(
            "memory-search",
            (
                'You MUST call memory.write key topic value {name:"alpha"}. Then memory.search '
                'query "alpha". Finally return ok=true.'
            ),
            lambda _workspace: None,
            lambda state: bool(state.memory),
        ),
        Case(
            "read-two-summarize",
            (
                "You MUST call fs.read on first.txt and second.txt. Then artifact.put name "
                "summary.txt with a combined summary. Finally return ok=true."
            ),
            lambda workspace: (
                (workspace / "first.txt").write_text("one", encoding="utf-8"),
                (workspace / "second.txt").write_text("two", encoding="utf-8"),
            ),
            lambda state: sum(1 for item in state.history if item.get("name") == "fs.read") >= 2,
        ),

        Case(
            "repair-code",
            (
                "You MUST call fs.read on calc.py and test_calc.py. Then fs.write calc.py "
                "with a corrected implementation of add. Then test.run target test_calc.py. "
                'Finally return {"ok":true,"summary":"..."} .'
            ),
            lambda workspace: (
                (workspace / "calc.py").write_text(
                    "def add(a, b):\n    return a - b\n", encoding="utf-8"
                ),
                (workspace / "test_calc.py").write_text(
                    "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                    encoding="utf-8",
                ),
            ),
            lambda state: any(item.get("name") == "test.run" for item in state.history)
            and "a + b" in (state.workspace / "calc.py").read_text(encoding="utf-8"),
        ),
        Case(
            "plan-replan",
            (
                'You MUST call plan.create goal "replan" steps ["one"]. Then plan.update '
                'with the plan id and steps ["one","two","three"]. Then plan.read. '
                "Finally return ok=true."
            ),
            lambda _workspace: None,
            lambda state: bool(state.plans)
            and len(next(iter(state.plans.values()))["steps"]) == 3,
        ),
        Case(
            "multi-file-compare",
            (
                "You MUST call fs.read on a.txt, b.txt and c.txt. Then artifact.put name "
                "compare.txt with a short comparison. Finally return ok=true."
            ),
            lambda workspace: (
                (workspace / "a.txt").write_text("A", encoding="utf-8"),
                (workspace / "b.txt").write_text("B", encoding="utf-8"),
                (workspace / "c.txt").write_text("C", encoding="utf-8"),
            ),
            lambda state: sum(1 for item in state.history if item.get("name") == "fs.read") >= 3,
        ),
        Case(
            "json-repair",
            (
                "You MUST call fs.write path result.json content '{\"x\": 1}'. Then "
                "verify.code path result.json required_keys ['x']. If it fails, fix and retry. "
                "Finally return ok=true."
            ),
            lambda _workspace: None,
            lambda state: any(item.get("name") == "verify.code" for item in state.history),
        ),
        Case(
            "context-plan-artifact",
            (
                'You MUST call context.inspect. Then plan.create goal "context" steps ["inspect"]. '
                "Then artifact.put name context.txt content 'ok'. Finally return ok=true."
            ),
            lambda _workspace: None,
            lambda state: any(item.get("name") == "context.inspect" for item in state.history),
        ),
    ]


class CaseAuditor:
    def __init__(self, llm: DeepSeekChatClient) -> None:
        self.inner = LLMAuditor(llm, min_score=2.0)
        self.last = None

    def __call__(self, task, output, trace):  # noqa: ANN001
        self.last = self.inner.audit(task.goal, output, trace=trace)
        if self.last.accepted:
            return []
        return self.last.problems or ["audit rejected"]


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )


def run_case(case: Case, root: Path, llm: DeepSeekChatClient) -> dict[str, Any]:
    workspace = root / case.name
    workspace.mkdir(parents=True, exist_ok=True)
    case.setup(workspace)
    state = GeneralState(workspace=workspace)
    started = time.perf_counter()
    case_auditor = CaseAuditor(llm)
    result = AgentKernel(llm, _runtime(), state).run(
        KernelTask(
            task_id=case.name,
            goal=case.goal,
            inputs={"workspace": str(workspace)},
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=8, max_usd=1.0, max_repair=1),
            trace_auditor=case_auditor,
        )
    )
    latency = (time.perf_counter() - started) * 1000
    audit = case_auditor.last
    verified = False
    try:
        verified = case.verify(state)
    except Exception:
        verified = False
    return {
        "case": case.name,
        "success": result.stop_reason == "final" and verified,
        "verified": verified,
        "stop_reason": result.stop_reason,
        "error_code": result.error_code,
        "steps": result.metrics.get("steps", 0),
        "tool_calls": result.metrics.get("tool_calls", 0),
        "tool_errors": result.metrics.get("tool_errors", 0),
        "repairs": result.metrics.get("repairs", 0),
        "audit_accepted": bool(audit and audit.accepted),
        "audit_scores": audit.scores if audit else {},
        "audit_problems": audit.problems if audit else [],
        "audit_calls": result.metrics.get("audit_calls", 0),
        "audit_failures": result.metrics.get("audit_failures", 0),
        "audit_repair_successes": result.metrics.get("audit_repair_successes", 0),
        "prompt_tokens": result.usage.get("prompt_tokens", 0),
        "completion_tokens": result.usage.get("completion_tokens", 0),
        "cost_usd": result.cost_usd,
        "latency_ms": latency,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=Path("D:/lit-agent-store/kernel-complex-metrics.sqlite"))
    parser.add_argument("--out", type=Path, default=Path("D:/lit-agent-store/kernel-complex.json"))
    args = parser.parse_args()
    db = Database(args.db)
    db.migrate()
    store = KernelMetricStore(db)
    llm = DeepSeekChatClient(load_llm_config())
    rows = []
    with tempfile.TemporaryDirectory() as temp:
        for case in build_cases():
            row = run_case(case, Path(temp), llm)
            result = row.pop("result")
            store.record(
                result,
                task_id=case.name,
                model=llm.config.model,
                schema_ok=row["success"],
                latency_ms=row["latency_ms"],
                metadata={"audit_accepted": row["audit_accepted"], "audit_scores": row["audit_scores"]},
            )
            rows.append(row)
            print(json.dumps({k: v for k, v in row.items() if k != "result"}, ensure_ascii=False))
    latencies = sorted(row["latency_ms"] for row in rows)
    summary = {
        "cases": len(rows),
        "success": sum(1 for row in rows if row["success"]),
        "success_rate": sum(1 for row in rows if row["success"]) / len(rows) if rows else 0.0,
        "audit_accepted": sum(1 for row in rows if row["audit_accepted"]),
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

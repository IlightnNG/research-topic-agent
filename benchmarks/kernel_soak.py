"""Real-LLM soak/concurrency probe for the generic AgentKernel."""

from __future__ import annotations

import argparse
import json
import statistics
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config
from lit_agent_v2.storage.db import Database
from lit_agent_v2.storage.kernel_metrics import KernelMetricStore
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {"type": "object", "required": ["ok"]}


class RealLLM:
    def __init__(self, model: str) -> None:
        self.client = DeepSeekChatClient(load_llm_config())
        self.model = model

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        return self.client.chat_json(messages, **kwargs)


def run_one(index: int, root: Path, llm: RealLLM) -> dict[str, Any]:
    state = GeneralState(workspace=root / f"task-{index}")
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    started = time.perf_counter()
    result = AgentKernel(llm, runtime, state).run(
        KernelTask(
            task_id=f"soak-{index}",
            goal="Call fs.list on '.' and then return final JSON with ok=true.",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=4),
        )
    )
    return {
        "index": index,
        "success": result.stop_reason == "final",
        "latency_ms": (time.perf_counter() - started) * 1000,
        "prompt_tokens": result.usage.get("prompt_tokens", 0),
        "completion_tokens": result.usage.get("completion_tokens", 0),
        "cost_usd": result.cost_usd,
        "result": result,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=int, default=8)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=Path, default=Path("D:/lit-agent-store/kernel-soak.json"))
    parser.add_argument("--db", type=Path, default=Path("D:/lit-agent-store/kernel-soak.sqlite"))
    args = parser.parse_args()
    db = Database(args.db)
    db.migrate()
    store = KernelMetricStore(db)
    llm = RealLLM(load_llm_config().model)
    rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            for row in pool.map(lambda i: run_one(i, root, llm), range(args.tasks)):
                result = row.pop("result")
                store.record(
                    result,
                    task_id=f"soak-{row['index']}",
                    model=llm.model,
                    schema_ok=row["success"],
                    latency_ms=row["latency_ms"],
                )
                rows.append(row)
    latencies = sorted(row["latency_ms"] for row in rows)
    summary = {
        "tasks": len(rows),
        "concurrency": args.concurrency,
        "success": sum(1 for row in rows if row["success"]),
        "latency_p50_ms": statistics.median(latencies),
        "latency_p95_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        "cost_usd": sum(row["cost_usd"] for row in rows),
        "results": rows,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, ensure_ascii=False))
    return 0 if summary["success"] == summary["tasks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

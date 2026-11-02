"""S6/S7: kernel hardening, checkpoint, scheduler, metrics, node entry."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.features import FeatureProfile
from lit_agent_v2.contracts.node import NodeContext, NodeSpec
from lit_agent_v2.contracts.tool import ToolContext, ToolSpec
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore, KernelCheckpoint
from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.node import KernelNodeAdapter
from lit_agent_v2.kernel.agent.observability import JsonlEventSink
from lit_agent_v2.kernel.agent.scheduler import schedule_tool_calls
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime


class FakeLLM:
    def __init__(self, actions: list[dict[str, Any]], *, fail_first: bool = False) -> None:
        self.actions = actions
        self.index = 0
        self.fail_first = fail_first
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        self.calls += 1
        if self.fail_first and self.calls == 1:
            raise TimeoutError("temporary")
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action, None


def _final() -> dict[str, Any]:
    return {"action": "final", "outputs": {"ok": True}}


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )


def test_parallel_scheduler_overlaps_safe_calls(tmp_path: Path) -> None:
    def slow(args: dict[str, Any], _context: ToolContext) -> dict[str, Any]:
        time.sleep(0.05)
        return {"value": args["value"]}

    registry = ToolRegistry(
        [
            ToolSpec(
                "slow",
                "slow read",
                {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
                {"type": "object", "required": ["value"]},
                context_handler=slow,
                parallel_safe=True,
            )
        ]
    )
    runtime = ToolRuntime(registry)
    calls = [
        {"id": f"c{i}", "name": "slow", "args": {"value": i}} for i in range(4)
    ]
    started = time.monotonic()
    results = schedule_tool_calls(
        runtime,
        calls,
        toolset="",
        context_for=lambda call: ToolContext(call_id=call["id"]),
        max_parallel=4,
    )
    elapsed = time.monotonic() - started
    assert [result.output["value"] for result in results] == [0, 1, 2, 3]
    assert elapsed < 0.18


def test_checkpoint_and_resume(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path / "checkpoints")
    state = GeneralState(workspace=tmp_path)
    state.history.append({"role": "tool", "call_id": "c1", "content": "partial"})
    store.save(
        KernelCheckpoint(
            task_id="resume-me",
            step=1,
            state=state.export(),
        )
    )
    runtime = _runtime(tmp_path)
    llm = FakeLLM([_final()])
    result = AgentKernel(llm, runtime, GeneralState(workspace=tmp_path), checkpoints=store).run(
        KernelTask(
            task_id="resume-me",
            goal="resume",
            output_schema={"type": "object", "required": ["ok"]},
            toolset="general",
            policy=KernelPolicy(max_steps=3),
        )
    )
    assert result.stop_reason == "final"
    assert result.steps == 2
    assert store.load("resume-me") is None


def test_model_retry_and_metrics(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    llm = FakeLLM([_final()], fail_first=True)
    result = AgentKernel(llm, runtime, GeneralState(workspace=tmp_path)).run(
        KernelTask(
            task_id="retry",
            goal="retry",
            output_schema={"type": "object", "required": ["ok"]},
            toolset="general",
            policy=KernelPolicy(max_steps=3, max_retries=1),
        )
    )
    assert result.stop_reason == "final"
    assert result.metrics["model_retries"] >= 1


def test_jsonl_event_sink(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    sink = JsonlEventSink(tmp_path / "kernel-events.jsonl")
    result = AgentKernel(FakeLLM([_final()]), runtime, GeneralState(workspace=tmp_path), events=sink).run(
        KernelTask(
            task_id="events",
            goal="events",
            output_schema={"type": "object", "required": ["ok"]},
            toolset="general",
        )
    )
    assert result.stop_reason == "final"
    lines = (tmp_path / "kernel-events.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"type": "kernel.started"' in line for line in lines)
    assert any('"type": "kernel.finished"' in line for line in lines)


def test_node_adapter_entrypoint(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    adapter = KernelNodeAdapter(FakeLLM([_final()]), runtime, workspace=tmp_path)
    node = NodeSpec(
        id="smoke",
        goal="return ok",
        tools=("fs.list",),
        output_schema={"type": "object", "required": ["ok"]},
    )
    result = adapter.run(
        node,
        NodeContext(
            run_id="run-1",
            node_id="smoke",
            goal=node.goal,
            features=FeatureProfile(),
        ),
    )
    assert result.output == {"ok": True}
    assert result.stop_reason == "final"
    assert result.checkpoint["steps"] == 1

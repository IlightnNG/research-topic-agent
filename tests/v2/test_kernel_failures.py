"""Kernel failure paths and persistent metrics."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore
from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.observability import MemoryEventSink
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.storage.db import Database
from lit_agent_v2.storage.kernel_metrics import KernelMetricStore
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {"type": "object", "required": ["ok"]}


class FakeLLM:
    def __init__(self, actions: list[Any]) -> None:
        self.actions = actions
        self.index = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action, None


def _call(call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"action": "tool", "calls": [{"id": call_id, "name": name, "args": args}]}


def _final() -> dict[str, Any]:
    return {"action": "final", "outputs": {"ok": True}}


def _runtime(tmp_path: Path) -> ToolRuntime:
    return ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )


def _run(tmp_path: Path, actions: list[Any], *, max_steps: int = 5) -> Any:
    return AgentKernel(
        FakeLLM(actions), _runtime(tmp_path), GeneralState(workspace=tmp_path)
    ).run(
        KernelTask(
            task_id=f"failure-{time.monotonic_ns()}",
            goal="failure path",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=max_steps, max_repair=0),
        )
    )


def test_invalid_action_fails(tmp_path: Path) -> None:
    result = _run(tmp_path, [[], []])
    assert result.stop_reason == "failed"
    assert result.error_code == "E_KERNEL_INVALID_ACTION"


def test_no_progress_fails(tmp_path: Path) -> None:
    action = _call("same", "fs.list", {"path": "."})
    result = _run(tmp_path, [action, action, action, action, action])
    assert result.stop_reason == "no_progress"
    assert result.error_code == "E_KERNEL_NO_PROGRESS"


def test_max_steps(tmp_path: Path) -> None:
    actions = [
        _call("a", "fs.write", {"path": "a.txt", "content": "a"}),
        _call("b", "fs.write", {"path": "b.txt", "content": "b"}),
    ]
    result = _run(tmp_path, actions, max_steps=2)
    assert result.stop_reason == "max_steps"
    assert result.error_code == "E_KERNEL_MAX_STEPS"


def test_output_schema_repair_exhausted(tmp_path: Path) -> None:
    result = _run(
        tmp_path,
        [
            {"action": "final", "outputs": {"wrong": True}},
            {"action": "final", "outputs": {"wrong": True}},
        ],
    )
    assert result.stop_reason == "failed"
    assert result.error_code == "E_KERNEL_REPAIR_EXHAUSTED"


def test_tool_timeout_is_observed(tmp_path: Path) -> None:
    registry = ToolRegistry(
        [
            ToolSpec(
                "slow.tool",
                "slow",
                {"type": "object"},
                {"type": "object"},
                timeout_s=0.01,
                handler=lambda _args: (time.sleep(0.1), {"ok": True})[1],
            )
        ]
    )
    runtime = ToolRuntime(registry, toolsets={"general": ("slow.tool",)})
    result = AgentKernel(
        FakeLLM([_call("t", "slow.tool", {}), _final()]),
        runtime,
        GeneralState(workspace=tmp_path),
    ).run(
        KernelTask(
            task_id="timeout",
            goal="timeout",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=3),
        )
    )
    assert result.stop_reason == "final"
    assert result.metrics["tool_errors"] == 1
    assert any(item.get("error_code") == "E_TOOL_TIMEOUT" for item in result.history)


def test_policy_denial_is_observed(tmp_path: Path) -> None:
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        policy=lambda _name, _args, _ctx: "blocked",
    )
    result = AgentKernel(
        FakeLLM([_call("t", "fs.list", {"path": "."}), _final()]),
        runtime,
        GeneralState(workspace=tmp_path),
    ).run(
        KernelTask(
            task_id="policy",
            goal="policy",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=3),
        )
    )
    assert result.metrics["tool_errors"] == 1
    assert any(item.get("error_code") == "E_TOOL_POLICY_DENIED" for item in result.history)


def test_streaming_callback_and_event(tmp_path: Path) -> None:
    class StreamingLLM(FakeLLM):
        def stream_json(self, messages, *, on_delta=None, **kwargs):  # noqa: ANN001, ARG002
            if on_delta is not None:
                on_delta('{"action":"final"')
                on_delta(',"outputs":{"ok":true}}')
            return _final(), None

    events = MemoryEventSink()
    received: list[str] = []
    result = AgentKernel(
        StreamingLLM([_final()]),
        _runtime(tmp_path),
        GeneralState(workspace=tmp_path),
        events=events,
    ).run(
        KernelTask(
            task_id="stream",
            goal="stream",
            output_schema=OUTPUT,
            toolset="general",
        ),
        on_delta=received.append,
    )
    assert result.stop_reason == "final"
    assert "".join(received).startswith('{"action":"final"')
    assert any(event.type == "kernel.assistant_delta" for event in events.events)


def test_persistent_metrics_store(tmp_path: Path) -> None:
    db = Database(tmp_path / "metrics.sqlite")
    db.migrate()
    result = _run(tmp_path, [_final()])
    store = KernelMetricStore(db)
    metric_id = store.record(
        result,
        task_id="metrics",
        model="fake",
        schema_ok=True,
        latency_ms=12.5,
    )
    assert metric_id
    summary = store.summary()
    assert summary["n"] == 1
    assert summary["successes"] == 1


def test_audit_repair_metrics(tmp_path: Path) -> None:
    calls = {"n": 0}

    def auditor(_task, _output):  # noqa: ANN001
        calls["n"] += 1
        return ["audit rejected"] if calls["n"] == 1 else []

    result = AgentKernel(
        FakeLLM([_final(), _final()]),
        _runtime(tmp_path),
        GeneralState(workspace=tmp_path),
    ).run(
        KernelTask(
            task_id="audit",
            goal="audit",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=4, max_repair=1),
            auditor=auditor,
        )
    )
    assert result.stop_reason == "final"
    assert result.metrics["audit_calls"] == 2
    assert result.metrics["audit_failures"] == 1
    assert result.metrics["repairs"] == 1


def test_corrupt_checkpoint_is_ignored(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path / "checkpoints")
    path = tmp_path / "checkpoints" / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    assert store.load("broken") is None

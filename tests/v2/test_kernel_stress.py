"""S9: long context, concurrency and crash/resume stress."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore
from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {"type": "object", "required": ["ok"]}


class FinalLLM:
    def __init__(self) -> None:
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        self.calls += 1
        return {"action": "final", "outputs": {"ok": True}}, None


class OneToolThenFinal:
    def __init__(self, stop_flag: list[bool]) -> None:
        self.calls = 0
        self.stop_flag = stop_flag

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        self.calls += 1
        if self.calls == 1:
            self.stop_flag[0] = True
            return {
                "action": "tool",
                "calls": [{"id": "c1", "name": "fs.list", "args": {"path": "."}}],
            }, None
        return {"action": "final", "outputs": {"ok": True}}, None


def _runtime() -> ToolRuntime:
    return ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )


def test_long_context_auto_compacts(tmp_path: Path) -> None:
    state = GeneralState(workspace=tmp_path)
    state.history.extend(
        [{"role": "tool", "call_id": f"c{i}", "content": "x" * 1000} for i in range(100)]
    )
    result = AgentKernel(FinalLLM(), _runtime(), state).run(
        KernelTask(
            task_id="long",
            goal="finish",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(
                max_steps=2,
                soft_history_chars=1000,
                hard_history_chars=2000,
            ),
        )
    )
    assert result.stop_reason == "final"
    assert result.metrics["compactions"] >= 1


def test_concurrent_kernels(tmp_path: Path) -> None:
    def task(index: int) -> str:
        workspace = tmp_path / f"task-{index}"
        state = GeneralState(workspace=workspace)
        result = AgentKernel(FinalLLM(), _runtime(), state).run(
            KernelTask(
                task_id=f"task-{index}",
                goal=f"task {index}",
                output_schema=OUTPUT,
                toolset="general",
            )
        )
        return result.stop_reason

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(task, range(16)))
    assert results == ["final"] * 16


def test_crash_then_resume(tmp_path: Path) -> None:
    store = FileCheckpointStore(tmp_path / "checkpoints")
    state = GeneralState(workspace=tmp_path)
    stop_flag = [False]
    first = AgentKernel(
        OneToolThenFinal(stop_flag),
        _runtime(),
        state,
        should_stop=lambda: stop_flag[0],
        checkpoints=store,
    ).run(
        KernelTask(
            task_id="crash",
            goal="crash",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=4),
        )
    )
    assert first.stop_reason == "cancelled"
    assert store.load("crash") is not None

    second = AgentKernel(
        FinalLLM(),
        _runtime(),
        GeneralState(workspace=tmp_path),
        checkpoints=store,
    ).run(
        KernelTask(
            task_id="crash",
            goal="resume",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=3),
        )
    )
    assert second.stop_reason == "final"
    assert second.steps == 2
    assert store.load("crash") is None

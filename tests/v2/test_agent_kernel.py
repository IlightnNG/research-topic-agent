"""S4/S5: generic AgentKernel and kernel-only acceptance tasks A-E."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.tools.general import GENERAL_TOOLSET, build_general_tools
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime

OUTPUT = {
    "type": "object",
    "properties": {"ok": {"type": "boolean"}},
    "required": ["ok"],
}


class ScriptedLLM:
    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.index = 0
        self.messages: list[list[dict[str, str]]] = []

    def chat_json(self, messages, **kwargs):  # noqa: ANN001, ARG002
        self.messages.append(messages)
        action = self.actions[min(self.index, len(self.actions) - 1)]
        self.index += 1
        return action, None


def _call(call_id: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    return {"action": "tool", "calls": [{"id": call_id, "name": name, "args": args}]}


def _final(ok: bool = True) -> dict[str, Any]:
    return {"action": "final", "outputs": {"ok": ok}}


def _run(tmp_path: Path, actions: list[dict[str, Any]], *, name: str = "task") -> tuple:
    state = GeneralState(workspace=tmp_path)
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    llm = ScriptedLLM(actions)
    kernel = AgentKernel(llm, runtime, state)
    result = kernel.run(
        KernelTask(
            task_id=name,
            goal="complete the task",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=10),
        )
    )
    return result, state, llm


def test_kernel_task_a_workspace_analysis(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    actions = [
        _call("p", "plan.create", {"goal": "analyze", "steps": ["list", "read", "write"]}),
        _call("l", "fs.list", {"path": "."}),
        _call("r", "fs.read", {"path": "README.md"}),
        _call("a", "artifact.put", {"name": "analysis.txt", "content": "workspace analyzed"}),
        _final(),
    ]
    result, state, _ = _run(tmp_path, actions, name="task-a")
    assert result.stop_reason == "final"
    assert result.output == {"ok": True}
    assert state.plans
    assert any(item.get("role") == "tool" for item in state.history)
    assert list(state.artifacts.glob("*analysis.txt"))


def test_kernel_task_b_memory_brief(tmp_path: Path) -> None:
    actions = [
        _call(
            "m",
            "memory.write",
            {"key": "constraint", "value": {"text": "use only local evidence"}},
        ),
        _call("s", "memory.search", {"query": "local"}),
        _call("a", "artifact.put", {"name": "brief.md", "content": "# brief"}),
        _final(),
    ]
    result, state, _ = _run(tmp_path, actions, name="task-b")
    assert result.stop_reason == "final"
    assert state.memory


def test_kernel_task_c_run_tests(tmp_path: Path) -> None:
    (tmp_path / "test_sample.py").write_text(
        "def test_ok():\n    assert True\n", encoding="utf-8"
    )
    actions = [
        _call("w", "fs.write", {"path": "test_sample.py", "content": "def test_ok():\n    assert True\n"}),
        _call("t", "test.run", {"target": "test_sample.py"}),
        _call("v", "verify.code", {"path": "test_sample.py"}),
        _final(),
    ]
    result, _, _ = _run(tmp_path, actions, name="task-c")
    assert result.stop_reason == "final"
    assert any(item.get("name") == "test.run" for item in result.history)


def test_kernel_task_d_structured_extract(tmp_path: Path) -> None:
    (tmp_path / "input.txt").write_text("alpha=1\nbeta=2\n", encoding="utf-8")
    actions = [
        _call("r", "fs.read", {"path": "input.txt"}),
        _call(
            "a",
            "artifact.put",
            {"name": "extract.json", "content": '{"alpha": 1, "beta": 2}'},
        ),
        _call("v", "verify.code", {"path": "artifacts", "required_keys": []}),
        _final(),
    ]
    result, state, _ = _run(tmp_path, actions, name="task-d")
    assert result.stop_reason == "final"
    assert list(state.artifacts.glob("*extract.json"))


def test_kernel_task_e_context_compaction(tmp_path: Path) -> None:
    state = GeneralState(workspace=tmp_path)
    state.history.extend(
        [{"role": "tool", "call_id": f"c{i}", "content": "z" * 500} for i in range(20)]
    )
    runtime = ToolRuntime(
        ToolRegistry(build_general_tools()),
        toolsets={"general": GENERAL_TOOLSET},
        default_toolset="general",
    )
    llm = ScriptedLLM(
        [
            _call("x", "context.compact", {"keep_recent": 4}),
            _call("i", "context.inspect", {}),
            _final(),
        ]
    )
    result = AgentKernel(llm, runtime, state).run(
        KernelTask(
            task_id="task-e",
            goal="compress and finish",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=6),
        )
    )
    assert result.stop_reason == "final"
    assert state.compaction_count == 1
    assert result.steps == 3

    resumed = AgentKernel(ScriptedLLM([_final()]), runtime, state).run(
        KernelTask(
            task_id="task-e-resume",
            goal="continue after checkpoint",
            output_schema=OUTPUT,
            toolset="general",
            policy=KernelPolicy(max_steps=2),
        )
    )
    assert resumed.stop_reason == "final"


def test_kernel_repair_loop(tmp_path: Path) -> None:
    actions = [
        {"action": "final", "outputs": {"wrong": True}},
        _final(),
    ]
    result, _, llm = _run(tmp_path, actions, name="repair")
    assert result.stop_reason == "final"
    assert len(llm.messages) == 2
    assert "output rejected" in llm.messages[1][-1]["content"]

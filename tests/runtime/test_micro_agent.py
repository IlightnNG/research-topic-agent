"""3.0 / S2 验收：MicroAgent 六条路径 + 相位分离 + 状态隔离。"""

from __future__ import annotations

from typing import Any

from lit_agent.contracts.goals import NodeGoal
from lit_agent.runtime.micro_agent import LoopState, MicroAgent
from lit_agent.tools.registry import ToolResult
from lit_agent.tools.spec import ToolRuntime, ToolSpec

GOAL = NodeGoal(
    name="analysis",
    objective="抽取带引用的结论",
    postconditions=("citation_integrity",),
    tools=("echo",),
    max_steps=3,
    max_usd=1.0,
    autonomy="L2",
)


class Scripted:
    """按脚本依次返回动作；用完后重复最后一个。"""

    def __init__(self, actions: list[dict[str, Any]]) -> None:
        self.actions = actions
        self.calls = 0

    def __call__(self, messages: list[dict[str, str]], goal: NodeGoal) -> dict[str, Any]:
        self.calls += 1
        return self.actions[min(self.calls - 1, len(self.actions) - 1)]


def runtime(*, ok: bool = True, cost: float = 0.0, output: Any = None) -> ToolRuntime:
    rt = ToolRuntime()
    spec = ToolSpec(
        name="echo",
        description="echo",
        parameters={},
        output_schema={"type": "object", "required": ["ok"]},
    )
    rt.register(
        spec,
        lambda **_: {"ok": True} if output is None else output,
    )
    return rt


def test_final_path_stops_after_one_step() -> None:
    agent = MicroAgent(completer=Scripted([{"action": "final", "outputs": {"answer": 1}}]), tools=runtime())
    result = agent.run(GOAL)
    assert result.stop_reason == "final"
    assert result.outputs == {"answer": 1}
    assert result.steps_used == 1


def test_postcondition_path_after_tool() -> None:
    rt = runtime(output={"ok": True, "value": 42})
    agent = MicroAgent(
        completer=Scripted([{"action": "tool", "tool": "echo", "args": {}}]),
        tools=rt,
        postcondition=lambda loop: (bool(loop.trace[-1]["output"].get("ok")), []),
    )
    result = agent.run(GOAL)
    assert result.stop_reason == "postcondition"
    assert result.steps_used == 1


def test_replan_then_succeed() -> None:
    rt = ToolRuntime()
    calls = {"n": 0}

    def echo(**_: Any) -> dict[str, Any]:
        calls["n"] += 1
        return {"ok": calls["n"] >= 2}

    rt.register(
        ToolSpec(name="echo", description="e", output_schema={"type": "object", "required": ["ok"]}),
        echo,
    )
    agent = MicroAgent(
        completer=Scripted(
            [
                {"action": "tool", "tool": "echo", "args": {"attempt": 1}},
                {"action": "tool", "tool": "echo", "args": {"attempt": 2}},
            ]
        ),
        tools=rt,
        postcondition=lambda loop: (bool(loop.trace[-1]["output"].get("ok")), []),
    )
    result = agent.run(GOAL)
    assert result.stop_reason == "postcondition"
    assert result.steps_used == 2
    assert calls["n"] == 2


def test_budget_stop() -> None:
    goal = NodeGoal(
        name="g", objective="o", postconditions=("schema",), tools=("echo",), max_steps=3, max_usd=0.01
    )
    rt = ToolRuntime()
    rt.register(
        ToolSpec(name="echo", description="e", output_schema={"type": "object", "required": ["ok"]}),
        lambda **_: {"ok": False},
    )
    # 用 post 钩子给结果标注成本，验证"下一轮开始前预算检查"生效
    rt.add_post(
        lambda spec, args, result: ToolResult(
            ok=result.ok,
            output=result.output,
            error_code=result.error_code,
            meta={**result.meta, "cost_usd": 0.02},
        )
    )
    agent = MicroAgent(
        completer=Scripted([{"action": "tool", "tool": "echo", "args": {}}]),
        tools=rt,
        postcondition=lambda loop: (False, []),
    )
    result = agent.run(goal)
    assert result.stop_reason == "budget"
    assert result.steps_used == 1


def test_max_steps_stop() -> None:
    agent = MicroAgent(
        completer=Scripted(
            [
                {"action": "tool", "tool": "echo", "args": {"i": 1}},
                {"action": "tool", "tool": "echo", "args": {"i": 2}},
                {"action": "tool", "tool": "echo", "args": {"i": 3}},
            ]
        ),
        tools=runtime(),
        postcondition=lambda loop: (False, []),
    )
    result = agent.run(GOAL)
    assert result.stop_reason == "max_steps"
    assert result.steps_used == 3


def test_no_progress_stop() -> None:
    agent = MicroAgent(
        completer=Scripted([{"action": "tool", "tool": "echo", "args": {}}]),
        tools=runtime(),
        postcondition=lambda loop: (False, []),
    )
    result = agent.run(GOAL)
    assert result.stop_reason == "no_progress"
    assert result.steps_used == 3


def test_phases_are_separated() -> None:
    seen: list[str] = []

    def policy(goal: NodeGoal, loop: LoopState, state: dict[str, Any]) -> dict[str, Any]:
        seen.append("before_request")
        return {"intervened": True}

    agent = MicroAgent(
        completer=Scripted([{"action": "final", "outputs": {}}]),
        tools=runtime(),
        context_policy=policy,
    )
    result = agent.run(GOAL, {"topic_id": "t"})
    assert seen == ["before_request"]
    assert result.interventions == 1


def test_loop_states_are_isolated() -> None:
    agent = MicroAgent(completer=Scripted([{"action": "final", "outputs": {"n": 1}}]), tools=runtime())
    first = agent.run(GOAL)
    second = agent.run(GOAL)
    assert first.steps_used == second.steps_used == 1
    assert first is not second

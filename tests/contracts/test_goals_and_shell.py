"""3.0 / S1 验收：十个 NodeGoal + ShellSpec 契约（SH1/SH2 的最小子集）。"""

from __future__ import annotations

import inspect

import pytest

from lit_agent.contracts.goals import GOALS, NodeGoal, all_goals
from lit_agent.contracts.shell import ShellSpec, default_shell, shell_from_dict
from lit_agent.errors import E_CONFIG_INVALID, LitError
from lit_agent.graph.gates import GATE_NAMES
from lit_agent.graph.nodes import PHASE2_STAGES
from lit_agent.tools.spec import TOOL_NAMES


def test_ten_goals_cover_all_stages() -> None:
    assert list(GOALS) == list(PHASE2_STAGES)
    assert len(all_goals()) == 10


@pytest.mark.parametrize("goal", all_goals(), ids=[goal.name for goal in all_goals()])
def test_goal_is_valid(goal: NodeGoal) -> None:
    assert goal.validate() == []
    assert goal.postconditions
    assert len(goal.postconditions) <= 2
    assert set(goal.postconditions) <= set(GATE_NAMES)
    assert set(goal.tools) <= TOOL_NAMES
    assert 1 <= goal.max_steps <= 5


def test_goal_roundtrip() -> None:
    goal = GOALS["analysis"]
    assert NodeGoal.from_dict(goal.to_dict()) == goal


def test_default_shell_is_valid_and_stable() -> None:
    shell = default_shell()
    assert shell.validate() == []
    assert len(shell.goals) == 10
    again = default_shell()
    assert shell.hash == again.hash
    assert shell.hash != ""
    assert shell_from_dict(shell.to_dict()).hash == shell.hash


def test_shell_rejects_unknown_gate() -> None:
    bad = ShellSpec(
        name="bad",
        goals=(NodeGoal(name="x", objective="x", postconditions=("not_a_gate",)),),
    )
    problems = bad.validate()
    assert any("未知门禁" in item for item in problems)


def test_shell_from_dict_raises_config_invalid() -> None:
    with pytest.raises(LitError) as excinfo:
        shell_from_dict({"name": "bad", "goals": [{"name": "x", "objective": "x", "postconditions": []}]})
    assert excinfo.value.code == E_CONFIG_INVALID


def test_shell_hash_changes_with_config() -> None:
    base = default_shell()
    changed = ShellSpec(
        name=base.name,
        version="1.0.1",
        goals=base.goals,
        executor=base.executor,
    )
    assert base.hash != changed.hash


def test_shell_module_is_pure_data() -> None:
    """SH2：壳不 import IO/DB/LLM（静态检查 + 运行时无副作用）。"""
    import lit_agent.contracts.shell as module

    source = inspect.getsource(module)
    forbidden = ("lit_agent.db", "lit_agent.llm", "lit_agent.gateway", "import requests", "sqlite3")
    for token in forbidden:
        assert token not in source, f"壳不应依赖 {token}"
    shell = default_shell()
    assert shell.canonical() == shell.canonical()

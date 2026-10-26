"""3.5 / S27：ShellSpec 契约（SH1/SH2/SH3/SH5）。"""

from __future__ import annotations

import inspect

from lit_agent.contracts.goals import GOALS, NodeGoal
from lit_agent.contracts.shell import ShellSpec, default_shell, shell_from_dict
from lit_agent.eval.shell_metrics import shell_metrics


def test_shell_roundtrip_and_hash_stable() -> None:
    shell = default_shell()
    again = shell_from_dict(shell.to_dict())
    assert again.hash == shell.hash
    assert again.goals == shell.goals
    assert shell.validate() == []


def test_shell_hash_is_content_addressed() -> None:
    base = default_shell()
    changed = ShellSpec(name=base.name, version="9.9.9", goals=base.goals)
    assert changed.hash != base.hash


def test_shell_module_has_no_io_or_llm_imports() -> None:
    import lit_agent.contracts.shell as module

    source = inspect.getsource(module)
    for forbidden in ("lit_agent.db", "lit_agent.llm", "sqlite3", "requests"):
        assert forbidden not in source


def test_shell_is_removable_to_single_goal() -> None:
    single = ShellSpec(name="chat", goals=(GOALS["analysis"],))
    assert single.validate() == []
    assert len(single.goals) == 1
    assert single.goals[0] == GOALS["analysis"]


def test_shell_metrics_are_within_thickness_targets() -> None:
    metrics = shell_metrics(default_shell())
    assert metrics["shell_goals"] == 10
    assert metrics["shell_postconditions_max"] <= 2
    assert metrics["shell_loc"] <= 500
    assert metrics["shell_llm_calls_per_goal"] == 0.0


def test_goal_single_postcondition_ceiling() -> None:
    assert all(len(goal.postconditions) <= 2 for goal in GOALS.values())
    assert all(isinstance(goal, NodeGoal) for goal in GOALS.values())

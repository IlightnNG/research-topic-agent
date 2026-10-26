"""3.6 / S28：壳准入红线。"""

from __future__ import annotations

from lit_agent.contracts.goals import GOALS, NodeGoal
from lit_agent.contracts.shell import ShellSpec, default_shell
from lit_agent.eval.shell_admission import MAX_GOALS, admit


def test_default_shell_is_admitted() -> None:
    assert admit(default_shell()) == []


def test_missing_report_is_rejected() -> None:
    shell = ShellSpec(name="no-report", goals=(GOALS["retrieval"], GOALS["analysis"]))
    problems = admit(shell)
    assert any("缺少必要阶段" in item for item in problems)


def test_too_many_goals_is_rejected() -> None:
    goals = tuple(
        NodeGoal(name=f"g{index}", objective="x", postconditions=("schema",))
        for index in range(MAX_GOALS + 1)
    )
    problems = admit(ShellSpec(name="big", goals=goals))
    assert any("超过上限" in item for item in problems)


def test_budget_must_cover_goals() -> None:
    shell = ShellSpec(name="tight", goals=default_shell().goals, budget_llm_calls=2)
    problems = admit(shell)
    assert any("预算不足" in item for item in problems)

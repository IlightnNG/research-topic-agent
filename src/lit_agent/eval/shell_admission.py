"""3.6 / S28：壳准入（生成候选壳时的硬红线）。"""

from __future__ import annotations

from lit_agent.contracts.shell import ShellSpec

__all__ = ["MAX_GOALS", "REQUIRED_STAGES", "admit"]

MAX_GOALS = 10
REQUIRED_STAGES = frozenset({"retrieval", "analysis", "report"})


def admit(shell: ShellSpec) -> list[str]:
    """返回准入问题列表；空列表表示可以进入影子运行。"""
    problems = list(shell.validate())
    names = {goal.name for goal in shell.goals}
    missing = REQUIRED_STAGES - names
    if missing:
        problems.append(f"缺少必要阶段：{sorted(missing)}")
    if len(shell.goals) > MAX_GOALS:
        problems.append(f"goals 超过上限 {MAX_GOALS}（当前 {len(shell.goals)}）")
    if shell.budget_llm_calls < len(shell.goals):
        problems.append("LLM 预算不足以覆盖每个 goal 至少一次调用")
    return problems

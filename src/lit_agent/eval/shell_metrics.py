"""3.5 / S27：壳的厚度指标（SH1–SH5 的可计算部分）。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from lit_agent.contracts.shell import ShellSpec

__all__ = ["shell_metrics"]

ROOT = Path(__file__).resolve().parents[3]


def _loc() -> int:
    total = 0
    for rel in ("src/lit_agent/contracts/shell.py", "src/lit_agent/contracts/goals.py"):
        path = ROOT / rel
        if path.exists():
            total += len(path.read_text(encoding="utf-8").splitlines())
    return total


def shell_metrics(shell: ShellSpec, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    metrics = metrics or {}
    goals = len(shell.goals)
    postconditions_max = max((len(goal.postconditions) for goal in shell.goals), default=0)
    llm_calls = float(metrics.get("llm_calls_total") or metrics.get("llm_calls") or 0.0)
    return {
        "shell_hash": shell.hash,
        "shell_goals": goals,
        "shell_postconditions_max": postconditions_max,
        "shell_llm_calls_per_goal": round(llm_calls / goals, 3) if goals else 0.0,
        "shell_loc": _loc(),
        # 需要 LLM/tool span 才能精确计算；暂以 0 表示“未观测”，由 3.5 的 OTel 补齐
        "shell_overhead_ratio": float(metrics.get("shell_overhead_ratio") or 0.0),
    }

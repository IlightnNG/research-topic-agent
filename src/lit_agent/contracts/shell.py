"""ShellSpec（Phase 3 / §3.0）：任务相关的编排声明。

纯数据 + 纯函数：
- 可序列化、哈希稳定（S3）；
- 不含 IO/DB/LLM（S2）；
- 可整层删除，内核仍能跑单 Goal（S4）。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any, Literal

from lit_agent.contracts.goals import NodeGoal, all_goals

__all__ = ["ShellSpec", "default_shell", "shell_from_dict"]

Executor = Literal["graph", "goal_runner"]


@dataclass(frozen=True)
class ShellSpec:
    name: str
    version: str = "1.0.0"
    goals: tuple[NodeGoal, ...] = ()
    executor: Executor = "graph"
    budget_usd: float = 2.0
    budget_llm_calls: int = 12
    budget_wall_s: int = 900
    kernel_min: str = "3.0.0"
    notes: str = field(default="", compare=False)

    # ------------------------------------------------------------------ #
    def canonical(self) -> str:
        payload: dict[str, Any] = {
            "name": self.name,
            "version": self.version,
            "executor": self.executor,
            "budget": {
                "usd": self.budget_usd,
                "llm_calls": self.budget_llm_calls,
                "wall_s": self.budget_wall_s,
            },
            "kernel_min": self.kernel_min,
            "goals": [goal.to_dict() for goal in self.goals],
        }
        return json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    @property
    def hash(self) -> str:
        return hashlib.sha256(self.canonical().encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict[str, Any]:
        payload = json.loads(self.canonical())
        payload["hash"] = self.hash
        payload["notes"] = self.notes
        return payload

    def validate(self) -> list[str]:
        problems: list[str] = []
        if not self.name:
            problems.append("shell.name 不能为空")
        if not self.goals:
            problems.append("shell.goals 不能为空")
        ids = [goal.name for goal in self.goals]
        if len(ids) != len(set(ids)):
            problems.append(f"shell.goals 有重复 id：{ids}")
        for goal in self.goals:
            problems.extend(goal.validate())
        if self.executor not in ("graph", "goal_runner"):
            problems.append(f"未知 executor：{self.executor}")
        if self.budget_llm_calls < 1:
            problems.append("budget.llm_calls 必须 >= 1")
        if self.budget_usd <= 0:
            problems.append("budget.usd 必须 > 0")
        return problems


def default_shell() -> ShellSpec:
    """周报预设：十节点顺次执行（图执行器）。"""
    return ShellSpec(
        name="weekly-report",
        version="1.0.0",
        goals=tuple(all_goals()),
        executor="graph",
        notes="固定交付物；强引用约束",
    )


def shell_from_dict(data: dict[str, Any]) -> ShellSpec:
    goals = tuple(NodeGoal.from_dict(item) for item in data.get("goals") or ())
    budget = data.get("budget") or {}
    spec = ShellSpec(
        name=str(data.get("name") or ""),
        version=str(data.get("version") or "1.0.0"),
        goals=goals,
        executor=str(data.get("executor") or "graph"),  # type: ignore[arg-type]
        budget_usd=float(budget.get("usd") or 2.0),
        budget_llm_calls=int(budget.get("llm_calls") or 12),
        budget_wall_s=int(budget.get("wall_s") or 900),
        kernel_min=str(data.get("kernel_min") or "3.0.0"),
        notes=str(data.get("notes") or ""),
    )
    problems = spec.validate()
    if problems:
        from lit_agent.errors import E_CONFIG_INVALID, LitError

        raise LitError(E_CONFIG_INVALID, "; ".join(problems), context={"problems": problems})
    return spec

"""MicroAgent（Phase 3.0 / S2）：节点内的通用 plan + ReAct 运行时。

相位（冻结）：
    before_request → request → parse_actions → act/after_tool → after_action → replan

- **无状态**：所有可变状态在 `LoopState`，实例可复用/可并发；
- **有界**：`max_steps` + `goal.max_usd` + 无进展检测；
- **可测**：`completer` 与 `tools` 都通过注入，单测不用真实模型。
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lit_agent.contracts.goals import NodeGoal

__all__ = ["LoopState", "MicroAgent", "MicroResult"]

Completer = Callable[[list[dict[str, str]], NodeGoal], dict[str, Any]]
Postcondition = Callable[["LoopState"], tuple[bool, list[str]]]
ContextPolicy = Callable[[NodeGoal, "LoopState", dict[str, Any]], dict[str, Any]]


@dataclass
class LoopState:
    goal: NodeGoal
    step: int = 0
    trace: list[dict[str, Any]] = field(default_factory=list)
    cost_usd: float = 0.0
    interventions: int = 0
    last_action: str = ""
    repeat: int = 0

    @classmethod
    def new(cls, goal: NodeGoal) -> LoopState:
        return cls(goal=goal)


@dataclass
class MicroResult:
    outputs: dict[str, Any]
    steps_used: int
    stop_reason: str
    trace: list[dict[str, Any]]
    interventions: int
    cost_usd: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "outputs": self.outputs,
            "steps_used": self.steps_used,
            "stop_reason": self.stop_reason,
            "trace": self.trace,
            "interventions": self.interventions,
            "cost_usd": self.cost_usd,
        }


class MicroAgent:
    def __init__(
        self,
        *,
        completer: Completer,
        tools: Any,
        postcondition: Postcondition | None = None,
        context_policy: ContextPolicy | None = None,
        max_total_steps: int = 8,
        log: Any | None = None,
    ) -> None:
        self.completer = completer
        self.tools = tools
        self.postcondition = postcondition
        self.context_policy = context_policy
        self.max_total_steps = max_total_steps
        self.log = log

    # ------------------------------------------------------------------ #
    def run(self, goal: NodeGoal, state: dict[str, Any] | None = None) -> MicroResult:
        state = state or {}
        loop = LoopState.new(goal)
        outputs: dict[str, Any] = {}
        stop = "max_steps"

        for _ in range(min(goal.max_steps, self.max_total_steps)):
            if loop.cost_usd >= goal.max_usd > 0:
                stop = "budget"
                break
            loop.step += 1

            request = self.before_request(goal, loop, state)
            reply = self.completer(request["messages"], goal)
            action = self.parse_action(reply)

            if action["type"] == "final":
                outputs = dict(action.get("outputs") or {})
                stop = "final"
                loop.trace.append({"step": loop.step, "action": "final"})
                break

            result = self.act(action, loop)
            self.after_tool(loop, action, result)
            ok, reasons = self.after_action(goal, loop)
            if ok:
                outputs = dict(result.get("output") or {})
                stop = "postcondition"
                break

            self.replan(loop, action, reasons)
            if loop.repeat >= 2:
                stop = "no_progress"
                break

        return MicroResult(
            outputs=outputs,
            steps_used=loop.step,
            stop_reason=stop,
            trace=loop.trace,
            interventions=loop.interventions,
            cost_usd=round(loop.cost_usd, 6),
        )

    # ------------------------------------------------------------------ #
    def before_request(
        self, goal: NodeGoal, loop: LoopState, state: dict[str, Any]
    ) -> dict[str, Any]:
        """① pre-step：只做上下文（不调工具、不写业务表）。"""
        messages = [
            {"role": "system", "content": f"目标：{goal.objective}"},
            {"role": "user", "content": f"可用工具：{', '.join(goal.tools) or '无'}"},
        ]
        if self.context_policy is not None:
            patch = self.context_policy(goal, loop, state) or {}
            if patch.get("messages"):
                messages = patch["messages"]
            if patch.get("intervened"):
                loop.interventions += 1
        return {"messages": messages}

    def parse_action(self, reply: dict[str, Any]) -> dict[str, Any]:
        """③ 只解析，不执行。"""
        if not isinstance(reply, dict):
            return {"type": "final", "outputs": {}}
        if reply.get("action") == "final":
            return {"type": "final", "outputs": reply.get("outputs") or {}}
        return {
            "type": "tool",
            "tool": str(reply.get("tool") or ""),
            "args": dict(reply.get("args") or {}),
        }

    def act(self, action: dict[str, Any], loop: LoopState) -> dict[str, Any]:
        """④ 工具四段流水线（这里委托给 ToolRuntime）。"""
        budget = max(0.0, loop.goal.max_usd - loop.cost_usd)
        result = self.tools.call(
            action["tool"],
            args=action.get("args") or {},
            budget_usd=budget,
            log=self.log,
        )
        loop.cost_usd += float(result.meta.get("cost_usd") or 0.0)
        return {
            "ok": result.ok,
            "output": result.output,
            "error_code": result.error_code,
            "meta": result.meta,
        }

    def after_tool(
        self, loop: LoopState, action: dict[str, Any], result: dict[str, Any]
    ) -> None:
        """⑤ post 策略：只记录，不重写结果（重写在 ToolRuntime 的 post 钩子）。"""
        loop.trace.append(
            {
                "step": loop.step,
                "action": action.get("tool"),
                "ok": bool(result.get("ok")),
                "error_code": result.get("error_code"),
                "output": result.get("output"),
            }
        )

    def after_action(self, goal: NodeGoal, loop: LoopState) -> tuple[bool, list[str]]:
        """⑥ 门禁 = postcondition。"""
        if self.postcondition is None:
            return False, ["未配置 postcondition"]
        return self.postcondition(loop)

    def replan(
        self, loop: LoopState, action: dict[str, Any], reasons: list[str]
    ) -> None:
        """⑦ 失败 → 改计划（这里只统计重复，具体策略由调用方/模型决定）。"""
        current = f"{action.get('tool')}:{json.dumps(action.get('args') or {}, sort_keys=True, ensure_ascii=False)}"
        if current == loop.last_action:
            loop.repeat += 1
        else:
            loop.repeat = 0
        loop.last_action = current

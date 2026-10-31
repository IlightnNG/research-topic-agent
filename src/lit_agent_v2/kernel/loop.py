"""Bounded ReAct-compatible kernel with optional LLM completer."""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.kernel.checkpoint import KernelCheckpoint
from lit_agent_v2.kernel.llm import LLMUsage
from lit_agent_v2.kernel.tools import ToolBox, ToolResult, ToolSpec

__all__ = ["Goal", "Kernel", "KernelResult", "ToolBox", "ToolResult", "ToolSpec"]


@dataclass
class Goal:
    node_id: str
    objective: str
    system_prompt: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    max_steps: int = 6
    max_usd: float = 0.10
    timeout_s: float = 300.0
    prompt_version: str = "m1-p01"


@dataclass
class KernelResult:
    output: dict[str, Any]
    steps: list[dict[str, Any]] = field(default_factory=list)
    stop_reason: str = "final"
    cost_usd: float = 0.0
    usage: LLMUsage = field(default_factory=LLMUsage)


class Kernel:
    def __init__(self) -> None:
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def run(
        self,
        goal: Goal,
        toolbox: ToolBox,
        completer: Callable[[list[dict[str, Any]]], dict[str, Any]] | None = None,
        *,
        llm: Any | None = None,
        checkpoint: KernelCheckpoint | None = None,
        on_checkpoint: Callable[[KernelCheckpoint], None] | None = None,
        on_event: Callable[[str, dict[str, Any]], None] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> KernelResult:
        if completer is None and llm is None:
            return KernelResult({}, [], "failed")
        state = checkpoint or KernelCheckpoint(node_id=goal.node_id)
        history = list(state.history)
        trace = list(state.trace)
        cost = state.cost_usd
        usage = LLMUsage(
            prompt_tokens=state.prompt_tokens,
            completion_tokens=state.completion_tokens,
            model=getattr(getattr(llm, "config", None), "model", ""),
            prompt_version=goal.prompt_version,
        )
        started = time.monotonic()
        last_key = ""
        repeats = 0
        invalid = 0

        def emit(event: str, **payload: Any) -> None:
            if on_event is not None:
                on_event(event, payload)

        def finish(output, trace, reason, cost, usage, state, goal, on_checkpoint):
            emit("kernel.finished", stop_reason=reason, steps=state.step, cost_usd=cost)
            return self._finish(output, trace, reason, cost, usage, state, goal, on_checkpoint)

        emit("kernel.started", node_id=goal.node_id, objective=goal.objective)

        for step in range(state.step + 1, goal.max_steps + 1):
            emit("step.started", step=step)
            if self.cancelled or (should_stop is not None and should_stop()):
                return finish({}, trace, "cancelled", cost, usage, state, goal, on_checkpoint)
            if time.monotonic() - started > goal.timeout_s:
                return finish({}, trace, "timeout", cost, usage, state, goal, on_checkpoint)
            if cost >= goal.max_usd > 0:
                return finish({}, trace, "budget", cost, usage, state, goal, on_checkpoint)

            try:
                if completer is not None:
                    action = completer(history)
                else:
                    messages = self._messages(goal, toolbox, history)
                    action, step_usage = llm.chat_json(
                        messages,
                        prompt_version=goal.prompt_version,
                    )
                    usage = LLMUsage(
                        prompt_tokens=usage.prompt_tokens + step_usage.prompt_tokens,
                        completion_tokens=usage.completion_tokens + step_usage.completion_tokens,
                        model=step_usage.model or usage.model,
                        prompt_version=goal.prompt_version,
                    )
                    cost += step_usage.cost_usd
            except Exception as exc:  # noqa: BLE001
                emit("kernel.failed", step=step, error=type(exc).__name__)
                return finish({}, trace, "failed", cost, usage, state, goal, on_checkpoint)

            if not isinstance(action, dict):
                invalid += 1
                if invalid >= 2:
                    return finish({}, trace, "failed", cost, usage, state, goal, on_checkpoint)
                history.append({"error": "E_KERNEL_ACTION"})
                continue
            if action.get("action") == "final":
                return finish(
                    dict(action.get("outputs") or {}), trace, "final", cost, usage, state, goal, on_checkpoint
                )

            name = str(action.get("tool") or "")
            args = dict(action.get("args") or {})
            emit("tool.called", step=step, tool=name, args=args)
            result = toolbox.call(name, args)
            cost += result.cost_usd
            emit("tool.result", step=step, tool=name, ok=result.ok, error=result.error)
            trace.append({"step": step, "tool": name, "args": args, "ok": result.ok, "error": result.error})
            history.append(
                {
                    "step": step,
                    "tool": name,
                    "ok": result.ok,
                    "output": result.output,
                    "error": result.error,
                }
            )
            state.step = step
            state.history = history
            state.trace = trace
            state.cost_usd = cost
            state.prompt_tokens = usage.prompt_tokens
            state.completion_tokens = usage.completion_tokens
            if on_checkpoint is not None:
                on_checkpoint(state)
            if not result.ok:
                emit("kernel.failed", step=step, error=result.error)
                return finish({}, trace, "failed", cost, usage, state, goal, on_checkpoint)

            key = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
            repeats = repeats + 1 if key == last_key else 0
            last_key = key
            if repeats >= 1:
                return finish({}, trace, "no_progress", cost, usage, state, goal, on_checkpoint)

        return finish({}, trace, "max_steps", cost, usage, state, goal, on_checkpoint)

    def _messages(self, goal: Goal, toolbox: ToolBox, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        tools = [
            {"name": name, "description": (toolbox.spec(name).description if toolbox.spec(name) else "")}
            for name in toolbox.names()
        ]
        system = (
            (goal.system_prompt or "You are a bounded kernel worker.")
            + "\nUse only the provided tools. Do not invent evidence."
            + "\nReturn JSON only:"
            + '\n{"action":"tool","tool":name,"args":{...}}'
            + '\nor {"action":"final","outputs":{...}}'
        )
        user = {
            "objective": goal.objective,
            "context": goal.context,
            "tools": tools,
            "history": history[-8:],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
        ]

    def _finish(
        self,
        output: dict[str, Any],
        trace: list[dict[str, Any]],
        reason: str,
        cost: float,
        usage: LLMUsage,
        state: KernelCheckpoint,
        goal: Goal,
        on_checkpoint: Callable[[KernelCheckpoint], None] | None,
    ) -> KernelResult:
        state.trace = trace
        state.cost_usd = cost
        state.prompt_tokens = usage.prompt_tokens
        state.completion_tokens = usage.completion_tokens
        state.stop_reason = reason
        if on_checkpoint is not None:
            on_checkpoint(state)
        return KernelResult(output, trace, reason, cost, usage)

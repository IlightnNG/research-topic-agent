"""Bounded kernel loop (Phase 3.4 / S3-S5).

One kernel run executes one node goal. Checkpoints allow a crashed or paused
run to continue without repeating completed tool calls.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from lit_agent.kernel.checkpoint import CheckpointStore, KernelCheckpoint
from lit_agent.kernel.context import ContextLayers
from lit_agent.kernel.events import EventSink, emit
from lit_agent.kernel.tools import KernelTools
from lit_agent.kernel.types import KernelGoal, KernelResult, ToolCallRecord

__all__ = ["Kernel", "KernelCompleter", "LLMToolCompleter"]

KernelCompleter = Callable[[list[dict[str, Any]], KernelGoal], dict[str, Any]]


class LLMToolCompleter:
    """Default completer: ask the model to pick one allowed tool or finish."""

    def __init__(self, gateway: Any, tools: KernelTools) -> None:
        self.gateway = gateway
        self.tools = tools

    def __call__(self, history: list[dict[str, Any]], goal: KernelGoal) -> dict[str, Any]:
        specs = [
            {
                "name": name,
                "description": self.tools.spec(name).description,
                "parameters": self.tools.spec(name).parameters,
            }
            for name in goal.allowed_tools
            if name in self.tools.names()
        ]
        prompt = (
            "Choose the next action for this node. Return JSON only: "
            '{"action":"tool","tool":name,"args":{...}} or '
            '{"action":"final","outputs":{...}}. '
            "Only use allowed tools; finish when the objective is satisfied."
        )
        payload, _ = self.gateway.chat_json(
            [
                {"role": "system", "content": prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "objective": goal.objective,
                            "allowed_tools": goal.allowed_tools,
                            "tools": specs,
                            "history": history[-8:],
                        },
                        ensure_ascii=False,
                        default=str,
                    ),
                },
            ],
            max_tokens=500,
            agent="kernel",
        )
        return payload if isinstance(payload, dict) else {"action": "final", "outputs": {}}


class Kernel:
    def __init__(
        self,
        *,
        tools: KernelTools,
        gateway: Any | None = None,
        context: ContextLayers | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.tools = tools
        self.gateway = gateway
        self.context = context or ContextLayers()
        self.event_sink = event_sink
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(
        self,
        goal: KernelGoal,
        *,
        completer: KernelCompleter | None = None,
        checkpoint: CheckpointStore | None = None,
        resume: bool = False,
    ) -> KernelResult:
        if completer is None:
            if self.gateway is None:
                return KernelResult({}, [], 0, "failed")
            completer = LLMToolCompleter(self.gateway, self.tools)

        saved = checkpoint.load() if checkpoint is not None and resume else None
        if saved is not None:
            self.context = ContextLayers.from_dict(saved.context)
            trace = [ToolCallRecord(**item) for item in saved.trace]
            step = saved.step
            cost = saved.cost_usd
            history = [
                {"tool": item.name, "args": item.args, "ok": item.ok, "output": item.output}
                for item in trace
            ]
            if saved.stop_reason == "final":
                return KernelResult(
                    saved.output, trace, step, "final", cost
                )
        else:
            trace = []
            step = 0
            cost = 0.0
            history = []

        started = time.monotonic()
        emit(self.event_sink, "kernel.started", node_id=goal.node_id, goal=goal.objective)

        for _ in range(step + 1, max(1, goal.max_steps) + 1):
            step += 1
            if self._cancelled:
                return self._finish(goal, {}, trace, step - 1, "cancelled", cost, checkpoint)
            if time.monotonic() - started > goal.timeout_s:
                return self._finish(goal, {}, trace, step - 1, "timeout", cost, checkpoint)
            if cost >= goal.max_usd > 0:
                return self._finish(goal, {}, trace, step - 1, "budget", cost, checkpoint)

            try:
                reply = completer(history, goal)
            except Exception:  # noqa: BLE001 - checkpoint the failed step, caller decides
                self._save(goal, step - 1, trace, {}, "failed", cost, checkpoint)
                return self._finish(goal, {}, trace, step - 1, "failed", cost, checkpoint)
            if not isinstance(reply, dict):
                return self._finish(goal, {}, trace, step - 1, "failed", cost, checkpoint)
            if reply.get("action") == "final":
                output = dict(reply.get("outputs") or {})
                return self._finish(goal, output, trace, step, "final", cost, checkpoint)

            name = str(reply.get("tool") or "")
            args = dict(reply.get("args") or {})
            if not name or name not in goal.allowed_tools:
                trace.append(
                    ToolCallRecord(
                        name=name or "<missing>",
                        args=args,
                        ok=False,
                        error_code="E_TOOL_NOT_ALLOWED",
                    )
                )
                return self._finish(goal, {}, trace, step, "failed", cost, checkpoint)

            result = self.tools.call(name, args)
            cost += float(getattr(result, "meta", {}).get("cost_usd") or 0.0)
            trace.append(
                ToolCallRecord(
                    name=name,
                    args=args,
                    ok=bool(result.ok),
                    error_code=result.error_code,
                    output=result.output,
                )
            )
            history.append(
                {"tool": name, "args": args, "ok": bool(result.ok), "output": result.output}
            )
            self.context.working["last_tool"] = name
            self.context.working["last_output"] = result.output
            self._save(goal, step, trace, {}, "failed", cost, checkpoint)

            key = f"{name}:{json.dumps(args, sort_keys=True, ensure_ascii=False)}"
            if len(history) >= 2:
                previous = history[-2]
                previous_key = f"{previous['tool']}:{json.dumps(previous['args'], sort_keys=True, ensure_ascii=False)}"
                if key == previous_key:
                    return self._finish(goal, {}, trace, step, "no_progress", cost, checkpoint)

        return self._finish(goal, {}, trace, goal.max_steps, "max_steps", cost, checkpoint)

    def _save(
        self,
        goal: KernelGoal,
        step: int,
        trace: list[ToolCallRecord],
        output: dict[str, Any],
        reason: str,
        cost: float,
        checkpoint: CheckpointStore | None,
    ) -> None:
        if checkpoint is None:
            return
        checkpoint.save(
            KernelCheckpoint(
                goal=goal.to_dict(),
                step=step,
                trace=[item.to_dict() for item in trace],
                output=output,
                stop_reason=reason,  # type: ignore[arg-type]
                cost_usd=cost,
                context=self.context.to_dict(),
            )
        )

    def _finish(
        self,
        goal: KernelGoal,
        output: dict[str, Any],
        trace: list[ToolCallRecord],
        steps: int,
        reason: str,
        cost: float,
        checkpoint: CheckpointStore | None,
    ) -> KernelResult:
        self._save(goal, steps, trace, output, reason, cost, checkpoint)
        emit(
            self.event_sink,
            "kernel.finished",
            node_id=goal.node_id,
            stop_reason=reason,
            steps=steps,
            cost_usd=round(cost, 6),
        )
        return KernelResult(
            output=output,
            trace=trace,
            steps_used=steps,
            stop_reason=reason,  # type: ignore[arg-type]
            cost_usd=round(cost, 6),
        )

"""A small, domain-agnostic AgentKernel loop.

The kernel knows KernelTask, ToolRuntime and GeneralState only. It has no
report/paper/claim imports and can be exercised without a workflow.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from lit_agent_v2.contracts.tool import ToolContext
from lit_agent_v2.kernel.agent.task import KernelResult, KernelTask
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.runtime import ToolRuntime
from lit_agent_v2.tools.schema import validate_value

__all__ = ["AgentKernel"]


class AgentKernel:
    def __init__(
        self,
        llm: Any,
        tools: ToolRuntime,
        state: GeneralState,
        *,
        events: Any = None,
        should_stop: Callable[[], bool] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.state = state
        self.events = events
        self.should_stop = should_stop
        self.clock = clock or time.monotonic

    def run(self, task: KernelTask) -> KernelResult:
        history = self.state.history
        started = self.clock()
        cost = 0.0
        usage: dict[str, Any] = {}
        invalid = 0
        repair = 0
        self._emit("kernel.started", task=task.task_id, goal=task.goal)

        for step in range(1, task.policy.max_steps + 1):
            if self.should_stop is not None and self.should_stop():
                return self._finish(task, {}, history, step - 1, usage, cost, "cancelled")
            if self.clock() - started > task.policy.timeout_s:
                return self._finish(task, {}, history, step - 1, usage, cost, "timeout")
            if task.policy.max_usd > 0 and cost >= task.policy.max_usd:
                return self._finish(task, {}, history, step - 1, usage, cost, "budget")

            self._emit("kernel.step", task=task.task_id, step=step)
            messages = self._messages(task, history)
            try:
                action, step_usage = self.llm.chat_json(
                    messages,
                    max_tokens=task.policy.max_tokens,
                    temperature=0.1,
                )
            except Exception as exc:  # noqa: BLE001
                self._emit(
                    "kernel.failed", task=task.task_id, step=step, error=type(exc).__name__
                )
                return self._finish(task, {}, history, step, usage, cost, "failed")
            if step_usage is not None:
                usage["prompt_tokens"] = int(usage.get("prompt_tokens", 0)) + int(
                    getattr(step_usage, "prompt_tokens", 0) or 0
                )
                usage["completion_tokens"] = int(
                    usage.get("completion_tokens", 0)
                ) + int(getattr(step_usage, "completion_tokens", 0) or 0)
                cost += float(getattr(step_usage, "cost_usd", 0.0) or 0.0)

            if not isinstance(action, dict):
                invalid += 1
                history.append({"role": "system", "content": "invalid action: expected JSON object"})
                if invalid >= 2:
                    return self._finish(task, {}, history, step, usage, cost, "failed")
                continue

            if action.get("action") == "final":
                output = action.get("outputs")
                problems = self._validate_output(task, output)
                if problems and repair < task.policy.max_repair:
                    repair += 1
                    history.append(
                        {
                            "role": "system",
                            "content": "output rejected: " + "; ".join(problems) + ". Repair and final again.",
                        }
                    )
                    self._emit(
                        "kernel.repair", task=task.task_id, step=step, problems=problems
                    )
                    continue
                if problems:
                    return self._finish(task, {}, history, step, usage, cost, "failed")
                self._emit("kernel.finished", task=task.task_id, stop_reason="final")
                return self._finish(
                    task,
                    dict(output or {}),
                    history,
                    step,
                    usage,
                    cost,
                    "final",
                )

            calls = self._calls(action, step)
            if not calls:
                invalid += 1
                history.append({"role": "system", "content": "invalid action: no tool calls"})
                if invalid >= 2:
                    return self._finish(task, {}, history, step, usage, cost, "failed")
                continue

            invalid = 0
            history.append(
                {
                    "role": "assistant",
                    "tool_calls": calls,
                }
            )
            for call in calls:
                result = self.tools.call(
                    call["name"],
                    call["args"],
                    toolset=task.toolset,
                    context=ToolContext(
                        run_id=task.task_id,
                        node_id=task.task_id,
                        call_id=call["id"],
                        workspace=str(self.state.workspace),
                        signal=self.should_stop,
                        state=self.state,
                    ),
                )
                history.append(
                    {
                        "role": "tool",
                        "call_id": call["id"],
                        "name": call["name"],
                        "ok": result.ok,
                        "content": result.content
                        or json.dumps(result.output, ensure_ascii=False, default=str)[:4000],
                        "artifact_refs": result.artifact_refs,
                    }
                )
                self._emit(
                    "kernel.tool_result",
                    task=task.task_id,
                    step=step,
                    call_id=call["id"],
                    tool=call["name"],
                    ok=result.ok,
                )
                if not result.ok and result.error_code == "E_TOOL_TIMEOUT":
                    cost += result.cost_usd
            # Keep the same list object: context.compact mutates it in place.
            self.state.history[:] = history

        return self._finish(task, {}, history, task.policy.max_steps, usage, cost, "max_steps")

    def _validate_output(self, task: KernelTask, output: Any) -> list[str]:
        if not isinstance(output, dict):
            return ["outputs must be an object"]
        problems = validate_value("output", output, task.output_schema)
        if task.verifier is not None:
            try:
                problems.extend(task.verifier(output))
            except Exception as exc:  # noqa: BLE001
                problems.append(f"verifier_error:{type(exc).__name__}")
        return problems

    @staticmethod
    def _calls(action: dict[str, Any], step: int) -> list[dict[str, Any]]:
        raw = action.get("calls")
        if raw is None and action.get("tool"):
            raw = [{"id": f"call_{step}_1", "name": action.get("tool"), "args": action.get("args")}]
        if not isinstance(raw, list):
            return []
        calls = []
        for index, item in enumerate(raw[:16]):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("tool") or "")
            args = item.get("args")
            if name and isinstance(args, dict):
                calls.append(
                    {
                        "id": str(item.get("id") or f"call_{step}_{index + 1}"),
                        "name": name,
                        "args": args,
                    }
                )
        return calls

    def _messages(self, task: KernelTask, history: list[dict[str, Any]]) -> list[dict[str, str]]:
        tools = self.tools.visible(task.toolset)
        system = (
            "You are a general AgentKernel worker.\n"
            "You may plan, call tools, observe results, and revise the plan.\n"
            "Return JSON only: "
            '{"action":"tool","calls":[{"id":"call_1","name":"...","args":{}}]} '
            'or {"action":"final","outputs":{}}.\n'
            f"Task: {task.goal}\n"
            f"Output schema: {json.dumps(task.output_schema, ensure_ascii=False)}\n"
            f"Visible tools: {json.dumps(tools, ensure_ascii=False)}"
        )
        return [
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "task_id": task.task_id,
                        "inputs": task.inputs,
                        "plan": self.state.plans,
                        "history": history[-24:],
                    },
                    ensure_ascii=False,
                    default=str,
                ),
            },
        ]

    def _finish(
        self,
        task: KernelTask,
        output: dict[str, Any],
        history: list[dict[str, Any]],
        steps: int,
        usage: dict[str, Any],
        cost: float,
        stop_reason: str,
    ) -> KernelResult:
        plan = next(iter(self.state.plans.values()), None)
        self._emit(
            "kernel.finished",
            task=task.task_id,
            steps=steps,
            stop_reason=stop_reason,
        )
        return KernelResult(
            output=output,
            history=history,
            plan=plan,
            steps=steps,
            usage=usage,
            cost_usd=cost,
            stop_reason=stop_reason,
        )

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.events is not None:
            self.events.emit(event_type, **payload)

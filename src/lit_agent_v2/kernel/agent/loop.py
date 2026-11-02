"""A domain-agnostic AgentKernel loop.

The kernel knows KernelTask, ToolRuntime and GeneralState only. It has no
report/paper/claim imports and can be exercised without a workflow.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from typing import Any

from lit_agent_v2.contracts.tool import ToolContext
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore, KernelCheckpoint
from lit_agent_v2.kernel.agent.scheduler import schedule_tool_calls
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
        checkpoints: FileCheckpointStore | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.state = state
        self.events = events
        self.should_stop = should_stop
        self.clock = clock or time.monotonic
        self.checkpoints = checkpoints

    def run(
        self, task: KernelTask, *, on_delta: Callable[[str], None] | None = None
    ) -> KernelResult:
        history = self.state.history
        started = self.clock()
        cost = 0.0
        usage: dict[str, Any] = {}
        metrics = {
            "steps": 0,
            "tool_calls": 0,
            "tool_errors": 0,
            "model_retries": 0,
            "repairs": 0,
            "audit_calls": 0,
            "audit_failures": 0,
            "audit_repair_successes": 0,
            "compactions": 0,
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "cost_usd": 0.0,
        }
        invalid = 0
        repair = 0
        audit_failed_before = False
        last_signature = ""
        repeats = 0
        start_step = 1
        if self.checkpoints is not None:
            saved = self.checkpoints.load(task.task_id)
            if saved is not None:
                self.state.import_state(saved.state)
                start_step = saved.step + 1
                usage = dict(saved.usage)
                cost = saved.cost_usd
        self._emit("kernel.started", task=task.task_id, goal=task.goal)

        for step in range(start_step, task.policy.max_steps + 1):
            if self.should_stop is not None and self.should_stop():
                return self._finish(
                    task, {}, history, step - 1, usage, cost, metrics, "cancelled", "E_KERNEL_CANCELLED"
                )
            if self.clock() - started > task.policy.timeout_s:
                return self._finish(
                    task, {}, history, step - 1, usage, cost, metrics, "timeout", "E_KERNEL_TIMEOUT"
                )
            if task.policy.max_usd > 0 and cost >= task.policy.max_usd:
                return self._finish(
                    task, {}, history, step - 1, usage, cost, metrics, "budget", "E_KERNEL_BUDGET"
                )
            if metrics["tool_calls"] >= task.policy.max_tool_calls:
                return self._finish(
                    task, {}, history, step - 1, usage, cost, metrics, "tool_budget", "E_KERNEL_TOOL_BUDGET"
                )

            chars = len(json.dumps(history, ensure_ascii=False, default=str))
            if chars > task.policy.hard_history_chars:
                compacted = self.state.compact_context(keep_recent=6)
                metrics["compactions"] += 1
                self._emit("kernel.context_compacted", task=task.task_id, **compacted)
            elif chars > task.policy.soft_history_chars:
                compacted = self.state.compact_context(keep_recent=8)
                metrics["compactions"] += 1
                self._emit("kernel.context_compacted", task=task.task_id, **compacted)
            self.state.history[:] = history

            self._emit("kernel.step_started", task=task.task_id, step=step)
            messages = self._messages(task, history)
            action, step_usage = self._ask(task, messages, step, metrics, on_delta)
            if action is None:
                return self._finish(
                    task, {}, history, step, usage, cost, metrics, "failed", "E_MODEL_FAILED"
                )
            if step_usage is not None:
                usage["prompt_tokens"] = int(usage.get("prompt_tokens", 0)) + int(
                    getattr(step_usage, "prompt_tokens", 0) or 0
                )
                usage["completion_tokens"] = int(
                    usage.get("completion_tokens", 0)
                ) + int(getattr(step_usage, "completion_tokens", 0) or 0)
                step_cost = float(getattr(step_usage, "cost_usd", 0.0) or 0.0)
                cost += step_cost
                metrics["cost_usd"] = cost

            if not isinstance(action, dict):
                invalid += 1
                history.append({"role": "system", "content": "invalid action: expected JSON object"})
                if invalid >= 2:
                    return self._finish(
                        task, {}, history, step, usage, cost, metrics, "failed", "E_KERNEL_INVALID_ACTION"
                    )
                continue

            if action.get("action") == "final":
                output = action.get("outputs")
                problems = self._validate_output(task, output)
                audit_rejected = False
                if not problems and (task.trace_auditor is not None or task.auditor is not None):
                    metrics["audit_calls"] += 1
                    try:
                        if task.trace_auditor is not None:
                            audit_problems = task.trace_auditor(task, output, history)
                        else:
                            audit_problems = task.auditor(task, output)  # type: ignore[misc]
                        problems.extend(audit_problems or [])
                    except Exception as exc:  # noqa: BLE001
                        problems.append(f"audit_error:{type(exc).__name__}")
                    audit_rejected = bool(problems)
                    if audit_rejected:
                        metrics["audit_failures"] += 1
                        audit_failed_before = True
                if problems and repair < task.policy.max_repair:
                    repair += 1
                    metrics["repairs"] += 1
                    history.append(
                        {
                            "role": "system",
                            "content": "output rejected: " + "; ".join(problems) + ". Repair and final again.",
                        }
                    )
                    self._emit(
                        "kernel.repair", task=task.task_id, step=step, problems=problems
                    )
                    self._checkpoint(task, step, usage, cost)
                    continue
                if problems:
                    return self._finish(
                        task, {}, history, step, usage, cost, metrics, "failed", "E_KERNEL_REPAIR_EXHAUSTED"
                    )
                if audit_failed_before:
                    metrics["audit_repair_successes"] += 1
                return self._finish(
                    task, dict(output or {}), history, step, usage, cost, metrics, "final"
                )

            calls = self._calls(action, step)
            if not calls:
                invalid += 1
                history.append({"role": "system", "content": "invalid action: no tool calls"})
                if invalid >= 2:
                    return self._finish(
                        task, {}, history, step, usage, cost, metrics, "failed", "E_KERNEL_INVALID_ACTION"
                    )
                continue

            signature = json.dumps(
                [{"name": call["name"], "args": call["args"]} for call in calls],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            repeats = repeats + 1 if signature == last_signature else 0
            last_signature = signature
            if repeats == 2:
                history.append(
                    {
                        "role": "system",
                        "content": "duplicate tool call detected. Do not repeat it; use the observation and return final.",
                    }
                )
                self._emit("kernel.no_progress_warning", task=task.task_id, step=step)
                continue
            if repeats >= 4:
                return self._finish(
                    task, {}, history, step, usage, cost, metrics, "no_progress", "E_KERNEL_NO_PROGRESS"
                )
            invalid = 0
            history.append({"role": "assistant", "tool_calls": calls})
            metrics["tool_calls"] += len(calls)
            results = schedule_tool_calls(
                self.tools,
                calls,
                toolset=task.toolset,
                context_for=lambda call: ToolContext(
                    run_id=task.task_id,
                    node_id=task.task_id,
                    call_id=call["id"],
                    workspace=str(self.state.workspace),
                    signal=self.should_stop,
                    state=self.state,
                ),
                max_parallel=task.policy.max_parallel_tools,
            )
            for call, result in zip(calls, results, strict=True):
                if not result.ok:
                    metrics["tool_errors"] += 1
                history.append(
                    {
                        "role": "tool",
                        "call_id": call["id"],
                        "name": call["name"],
                        "ok": result.ok,
                        "content": result.content
                        or json.dumps(result.output, ensure_ascii=False, default=str)[:4000],
                        "artifact_refs": result.artifact_refs,
                        "error_code": result.error_code,
                    }
                )
                self._emit(
                    "kernel.tool_result",
                    task=task.task_id,
                    step=step,
                    call_id=call["id"],
                    tool=call["name"],
                    ok=result.ok,
                    error_code=result.error_code,
                )
            self.state.history[:] = history
            self._checkpoint(task, step, usage, cost)
            metrics["steps"] = step

        return self._finish(
            task, {}, history, task.policy.max_steps, usage, cost, metrics, "max_steps", "E_KERNEL_MAX_STEPS"
        )

    def _ask(
        self,
        task: KernelTask,
        messages: list[dict[str, str]],
        step: int,
        metrics: dict[str, Any],
        on_delta: Callable[[str], None] | None,
    ) -> tuple[dict[str, Any] | None, Any]:
        streamer = getattr(self.llm, "stream_json", None)
        for attempt in range(task.policy.max_retries + 1):
            try:
                if on_delta is not None and callable(streamer):
                    def forward(piece: str) -> None:
                        self._emit(
                            "kernel.assistant_delta", task=task.task_id, step=step, text=piece
                        )
                        on_delta(piece)

                    return streamer(
                        messages,
                        on_delta=forward,
                        max_tokens=task.policy.max_tokens,
                        temperature=0.1,
                    )
                return self.llm.chat_json(
                    messages,
                    max_tokens=task.policy.max_tokens,
                    temperature=0.1,
                )
            except Exception as exc:  # noqa: BLE001
                metrics["model_retries"] += 1
                self._emit(
                    "kernel.model_retry",
                    task=task.task_id,
                    step=step,
                    attempt=attempt + 1,
                    error=type(exc).__name__,
                )
                if attempt >= task.policy.max_retries:
                    return None, None
                time.sleep(min(2.0, 0.1 * (2**attempt)))
        return None, None

    def _checkpoint(
        self, task: KernelTask, step: int, usage: dict[str, Any], cost: float
    ) -> None:
        if self.checkpoints is None:
            return
        self.checkpoints.save(
            KernelCheckpoint(
                task_id=task.task_id,
                step=step,
                state=self.state.export(),
                usage=usage,
                cost_usd=cost,
            )
        )
        self._emit("kernel.checkpoint", task=task.task_id, step=step)

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
        metrics: dict[str, Any],
        stop_reason: str,
        error_code: str | None = None,
    ) -> KernelResult:
        metrics = dict(metrics)
        metrics["steps"] = steps
        metrics["cost_usd"] = cost
        plan = next(iter(self.state.plans.values()), None)
        self._emit(
            "kernel.finished",
            task=task.task_id,
            steps=steps,
            stop_reason=stop_reason,
            error_code=error_code,
            metrics=metrics,
        )
        if self.checkpoints is not None:
            if stop_reason == "final":
                self.checkpoints.clear(task.task_id)
            else:
                self._checkpoint(task, steps, usage, cost)
        return KernelResult(
            output=output,
            history=history,
            plan=plan,
            steps=steps,
            usage=usage,
            cost_usd=cost,
            stop_reason=stop_reason,
            error_code=error_code,
            metrics=metrics,
        )

    def _emit(self, event_type: str, **payload: Any) -> None:
        if self.events is not None:
            self.events.emit(event_type, **payload)

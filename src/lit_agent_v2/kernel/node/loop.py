"""Node Platform kernel: bounded ReAct loop over a ToolRegistry.

Design notes borrowed from DSH agent-loop:
- one model step can contain multiple tool calls;
- tool calls carry ids and result pairs;
- read-only calls may run concurrently, side-effecting calls are ordered;
- retries are bounded and explicit;
- tool outputs are pruned before entering model history;
- checkpoints are written at step boundaries.

This is intentionally smaller than DSH: no session store, no streaming
protocol, no subagents, no hook/waterfall system.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.contracts.tool import ToolResult
from lit_agent_v2.kernel.node.checkpoint import KernelCheckpoint
from lit_agent_v2.kernel.node.inbox import KernelInbox
from lit_agent_v2.kernel.node.ports import CheckpointPort, EventPort, LLMPort, ToolRegistryPort

__all__ = ["Kernel"]


class Kernel:
    def __init__(
        self,
        llm: LLMPort,
        tools: ToolRegistryPort,
        *,
        checkpoint_store: CheckpointPort | None = None,
        events: EventPort | None = None,
        clock: Callable[[], float] | None = None,
        max_retries: int = 2,
        max_parallel_tools: int = 4,
        max_tool_chars: int = 4000,
        max_history_chars: int = 12000,
        inbox: KernelInbox | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.checkpoint_store = checkpoint_store
        self.events = events
        self.clock = clock or time.monotonic
        self.max_retries = max(0, max_retries)
        self.max_parallel_tools = max(1, max_parallel_tools)
        self.max_tool_chars = max(256, max_tool_chars)
        self.max_history_chars = max(4096, max_history_chars)
        self.inbox = inbox or KernelInbox()
        self.should_stop = should_stop
        self._run_id = ""
        self._journal: list[dict[str, Any]] = []

    def steer(self, text: str) -> None:
        """Queue a message for the next step boundary."""
        self.inbox.push(text)

    def run(
        self,
        node: NodeSpec,
        context: NodeContext,
        *,
        checkpoint: KernelCheckpoint | None = None,
        should_stop: Callable[[], bool] | None = None,
        on_delta: Callable[[str], None] | None = None,
    ) -> NodeResult:
        self._run_id = context.run_id
        stop_check = should_stop or self.should_stop
        if checkpoint is None and self.checkpoint_store is not None:
            raw = self.checkpoint_store.load(context.run_id, node.id)
            if raw:
                checkpoint = KernelCheckpoint.from_dict(raw)
        state = checkpoint or KernelCheckpoint(node_id=node.id)
        history = list(state.history)
        state.history = history
        trace = list(state.trace)
        self._journal = list(state.journal)
        self._append("turn.started", 0, node_id=node.id)
        cost = state.cost_usd
        usage = dict(state.usage)
        started = self.clock()
        last_key = ""
        repeats = 0
        invalid = 0

        for step in range(state.step + 1, node.max_steps + 1):
            if stop_check is not None and stop_check():
                return self._finish(node, state, {}, trace, cost, usage, "cancelled")
            if self.clock() - started > node.timeout_s:
                return self._finish(node, state, {}, trace, cost, usage, "timeout")
            if node.max_usd > 0 and cost >= node.max_usd:
                return self._finish(node, state, {}, trace, cost, usage, "budget")
            self._emit("step.started", node, step=step)
            self._append("step.started", step)
            steering = self.inbox.drain()
            if steering:
                self._append("steering.consumed", step, messages=[item.text for item in steering])
                self._emit("steering.consumed", node, step=step, messages=[item.text for item in steering])

            action = None
            for attempt in range(self.max_retries + 1):
                try:
                    action, step_usage = self._ask(
                        node,
                        self._messages(node, context, history, steering, step),
                        step=step,
                        on_delta=on_delta,
                    )
                    usage = self._merge_usage(usage, step_usage)
                    cost += float(getattr(step_usage, "cost_usd", 0.0) or 0.0)
                    reasoning = str(getattr(step_usage, "reasoning", "") or "").strip()
                    if reasoning:
                        summary = reasoning[:1200]
                        self._append("thinking.summary", step, text=summary)
                        self._emit("thinking.summary", node, step=step, text=summary)
                    break
                except Exception as exc:  # noqa: BLE001
                    retryable = bool(getattr(exc, "retryable", False))
                    if not retryable or attempt >= self.max_retries:
                        self._emit("node.failed", node, step=step, error=type(exc).__name__)
                        self._append("kernel.failed", step, error=type(exc).__name__)
                        return self._finish(node, state, {}, trace, cost, usage, "failed")
                    self._append("kernel.retry", step, attempt=attempt + 1)
                    self._emit(
                        "kernel.retry",
                        node,
                        step=step,
                        attempt=attempt + 1,
                        error=type(exc).__name__,
                    )

            if not isinstance(action, dict):
                invalid += 1
                if invalid >= 2:
                    return self._finish(node, state, {}, trace, cost, usage, "failed")
                history.append({"role": "system", "content": "invalid action: expected JSON object"})
                continue
            if action.get("action") == "final":
                self._append("assistant.final", step)
                outputs = action.get("outputs")
                if not isinstance(outputs, dict):
                    invalid += 1
                    if invalid >= 2:
                        return self._finish(node, state, {}, trace, cost, usage, "failed")
                    continue
                return self._finish(node, state, outputs, trace, cost, usage, "final")

            calls = self._normalize_calls(action, step)
            if not calls:
                invalid += 1
                if invalid >= 2:
                    return self._finish(node, state, {}, trace, cost, usage, "failed")
                history.append({"role": "system", "content": "invalid action: no tool calls"})
                continue

            signature = json.dumps(
                [{"name": call["name"], "args": call["args"]} for call in calls],
                sort_keys=True,
                ensure_ascii=False,
                default=str,
            )
            repeats = repeats + 1 if signature == last_key else 0
            last_key = signature
            if repeats >= 1:
                return self._finish(node, state, {}, trace, cost, usage, "no_progress")

            for call in calls:
                if call["name"] not in node.tools or self.tools.spec(call["name"]) is None:
                    self._emit("node.failed", node, step=step, error="tool_not_allowed")
                    return self._finish(node, state, {}, trace, cost, usage, "failed")
            self._append("assistant.tool_calls", step, calls=calls)
            history.append({"role": "assistant", "tool_calls": calls})
            results = self._execute_calls(node, calls)
            for call, result in zip(calls, results, strict=True):
                cost += result.cost_usd
                trace.append(
                    {
                        "step": step,
                        "call_id": call["id"],
                        "tool": call["name"],
                        "ok": result.ok,
                        "error": result.error_code,
                    }
                )
                self._append("tool.result", step, call_id=call["id"], tool=call["name"], ok=result.ok, error=result.error_code)
                self._emit(
                    "tool.result",
                    node,
                    step=step,
                    tool=call["name"],
                    call_id=call["id"],
                    ok=result.ok,
                    error=result.error_code,
                    summary=self._summary(result),
                    duration_ms=result.duration_ms,
                )
                history.append(
                    {
                        "role": "tool",
                        "call_id": call["id"],
                        "name": call["name"],
                        "ok": result.ok,
                        "output": self._compact(result.output),
                        "error": result.error_code,
                    }
                )
                self._save(node, context, state, step, history, trace, cost, usage, None)
                if node.max_usd > 0 and cost >= node.max_usd:
                    self._append("kernel.budget", step, cost_usd=cost)
                    return self._finish(node, state, {}, trace, cost, usage, "budget")

            self._append("step.finished", step)
            self._save(node, context, state, step, history, trace, cost, usage, None)

        return self._finish(node, state, {}, trace, cost, usage, "max_steps")

    def _ask(
        self,
        node: NodeSpec,
        messages: list[dict[str, str]],
        *,
        step: int,
        on_delta: Callable[[str], None] | None,
    ) -> tuple[dict, Any]:
        streamer = getattr(self.llm, "stream_json", None)
        if on_delta is not None and callable(streamer):
            def forward(piece: str) -> None:
                self._emit("assistant.delta", node, step=step, text=piece)
                on_delta(piece)

            return streamer(
                messages,
                on_delta=forward,
                prompt_version=f"{node.id}-v1",
                max_tokens=node.max_tokens,
                temperature=0.1,
            )
        return self.llm.chat_json(
            messages,
            prompt_version=f"{node.id}-v1",
            max_tokens=node.max_tokens,
            temperature=0.1,
        )

    def _normalize_calls(self, action: dict[str, Any], step: int) -> list[dict[str, Any]]:
        raw = action.get("calls")
        if raw is None and action.get("tool"):
            raw = [{"id": f"call_{step}_1", "name": action.get("tool"), "args": action.get("args")}]
        if not isinstance(raw, list):
            return []
        calls: list[dict[str, Any]] = []
        for index, item in enumerate(raw[:16]):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("tool") or "")
            args = item.get("args")
            if not name or not isinstance(args, dict):
                continue
            calls.append(
                {
                    "id": str(item.get("id") or f"call_{step}_{index + 1}"),
                    "name": name,
                    "args": args,
                }
            )
        return calls

    def _execute_calls(
        self, node: NodeSpec, calls: list[dict[str, Any]]
    ) -> list[ToolResult]:
        specs = [self.tools.spec(call["name"]) for call in calls]
        parallel = all(spec is not None and not spec.side_effect for spec in specs)
        for call in calls:
            self._emit("tool.called", node, tool=call["name"], call_id=call["id"])
        if parallel and len(calls) > 1:
            with ThreadPoolExecutor(max_workers=min(self.max_parallel_tools, len(calls))) as pool:
                futures = [pool.submit(self._call_one, call) for call in calls]
                return [future.result() for future in futures]
        return [self._call_one(call) for call in calls]

    def _call_one(self, call: dict[str, Any]) -> ToolResult:
        try:
            return self.tools.call(call["name"], call["args"])
        except Exception as exc:  # noqa: BLE001
            return ToolResult(False, error_code=f"E_TOOL_EXCEPTION:{type(exc).__name__}")

    def _summary(self, result: ToolResult) -> str:
        if not result.ok:
            return result.error_code or "Tool failed"
        if not result.output:
            return "Completed"
        keys = ", ".join(list(result.output)[:4])
        return f"Completed: {keys}"[:240]

    def _messages(
        self,
        node: NodeSpec,
        context: NodeContext,
        history: list[dict[str, Any]],
        steering: list[Any],
        step: int,
    ) -> list[dict[str, str]]:
        tools = []
        for name in node.tools:
            spec = self.tools.spec(name)
            if spec is not None:
                tools.append(
                    {
                        "name": name,
                        "description": spec.description,
                        "input_schema": spec.input_schema,
                    }
                )
        system = (
            "You are a Node worker inside a fixed workflow.\n"
            "Use only the listed tools. Do not invent evidence.\n"
            "One assistant step may contain multiple tool calls.\n"
            "Return JSON only, one of:\n"
            '{"action":"tool","calls":[{"id":"call_1","name":"name","args":{}}]}\n'
            '{"action":"final","outputs":{}}\n'
            f"Node: {node.id}\nGoal: {node.goal}\n"
            f"Output schema: {json.dumps(node.output_schema, ensure_ascii=False)}\n"
            f"Allowed tools: {json.dumps(tools, ensure_ascii=False)}"
        )
        compacted = self._compact_history(history, step, node)
        user = {
            "run_id": context.run_id,
            "features": context.features.__dict__,
            "inputs": context.inputs,
            "steering": [item.text for item in steering],
            "history": compacted[-8:],
        }
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user, ensure_ascii=False, default=str)},
        ]

    def _compact_history(
        self, history: list[dict[str, Any]], step: int, node: NodeSpec
    ) -> list[dict[str, Any]]:
        text = json.dumps(history, ensure_ascii=False, default=str)
        if len(text) <= self.max_history_chars:
            return history
        keep = 6
        compacted: list[dict[str, Any]] = []
        before = len(text)
        for index, item in enumerate(history):
            if index < len(history) - keep and item.get("role") == "tool":
                pruned = dict(item)
                pruned["output"] = {"truncated": True, "reason": "history_compacted"}
                compacted.append(pruned)
            else:
                compacted.append(item)
        after = len(json.dumps(compacted, ensure_ascii=False, default=str))
        self._append("context.compacted", step, before=before, after=after)
        self._emit("context.compacted", node, step=step, before=before, after=after)
        return compacted

    def _compact(self, value: Any) -> Any:
        text = json.dumps(value, ensure_ascii=False, default=str)
        if len(text) <= self.max_tool_chars:
            return value
        head = text[: self.max_tool_chars // 2]
        tail = text[-self.max_tool_chars // 4 :]
        return {
            "truncated": True,
            "chars": len(text),
            "preview": f"{head}\n\n[... tool output pruned ...]\n\n{tail}",
        }

    def _merge_usage(self, current: dict[str, Any], step_usage: Any) -> dict[str, Any]:
        merged = dict(current)
        merged["prompt_tokens"] = int(merged.get("prompt_tokens", 0)) + int(
            getattr(step_usage, "prompt_tokens", 0) or 0
        )
        merged["completion_tokens"] = int(merged.get("completion_tokens", 0)) + int(
            getattr(step_usage, "completion_tokens", 0) or 0
        )
        merged["model"] = getattr(step_usage, "model", merged.get("model", ""))
        return merged

    def _save(
        self,
        node: NodeSpec,
        context: NodeContext,
        state: KernelCheckpoint,
        step: int,
        history: list[dict[str, Any]],
        trace: list[dict[str, Any]],
        cost: float,
        usage: dict[str, Any],
        stop_reason: str | None,
    ) -> None:
        state.step = step
        state.history = history
        state.trace = trace
        state.cost_usd = cost
        state.usage = usage
        state.journal = self._journal
        state.stop_reason = stop_reason
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(context.run_id, node.id, state.to_dict())

    def _finish(
        self,
        node: NodeSpec,
        state: KernelCheckpoint,
        output: dict[str, Any],
        trace: list[dict[str, Any]],
        cost: float,
        usage: dict[str, Any],
        reason: str,
    ) -> NodeResult:
        state.trace = trace
        state.cost_usd = cost
        state.usage = usage
        self._append("kernel.finished", state.step, reason=reason, cost_usd=cost)
        state.journal = self._journal
        state.stop_reason = reason
        if self.checkpoint_store is not None:
            self.checkpoint_store.save(self._run_id, state.node_id, state.to_dict())
        self._emit("node.finished", node, stop_reason=reason, cost_usd=cost)
        return NodeResult(
            output=output,
            trace=trace,
            usage=usage,
            cost_usd=cost,
            stop_reason=reason,
            checkpoint=state.to_dict(),
        )

    def _append(self, kind: str, step: int, **detail: Any) -> None:
        self._journal.append({"step": step, "kind": kind, "detail": detail})

    def _emit(self, event_type: str, node: NodeSpec | None, **payload: Any) -> None:
        if self.events is not None:
            self.events.emit(event_type, node_id=node.id if node is not None else None, **payload)

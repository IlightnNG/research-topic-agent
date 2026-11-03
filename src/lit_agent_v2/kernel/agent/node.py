"""Minimal Node entrypoint for the generic AgentKernel.

This adapter is deliberately not a WorkflowRunner. It lets one Node call the
generic kernel while the workflow layer is still frozen.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore
from lit_agent_v2.kernel.agent.loop import AgentKernel
from lit_agent_v2.kernel.agent.task import KernelPolicy, KernelTask
from lit_agent_v2.tools.general.state import GeneralState
from lit_agent_v2.tools.runtime import ToolRuntime

__all__ = ["KernelNodeAdapter"]


class _NodeEventSink:
    def __init__(self, sink: Any, node_id: str) -> None:
        self.sink = sink
        self.node_id = node_id

    def emit(self, event_type: str, **payload: Any) -> None:
        self.sink.emit(event_type, node_id=self.node_id, **payload)


class KernelNodeAdapter:
    def __init__(
        self,
        llm: Any,
        tools: ToolRuntime,
        *,
        workspace: str | Path,
        events: Any = None,
        checkpoints: FileCheckpointStore | None = None,
        policy: KernelPolicy | None = None,
        verifier: Callable[[dict[str, Any]], list[str]] | None = None,
        should_stop: Callable[[], bool] | None = None,
    ) -> None:
        self.llm = llm
        self.tools = tools
        self.workspace = Path(workspace)
        self.events = events
        self.checkpoints = checkpoints
        self.policy = policy or KernelPolicy()
        self.verifier = verifier
        self.should_stop = should_stop

    def run(self, node: NodeSpec, context: NodeContext) -> NodeResult:
        state = GeneralState(workspace=self.workspace)
        policy = replace(
            self.policy,
            max_steps=node.max_steps,
            max_usd=node.max_usd,
            max_tokens=node.max_tokens,
            timeout_s=node.timeout_s,
        )
        task = KernelTask(
            task_id=f"{context.run_id}:{node.id}",
            goal=node.goal,
            inputs=dict(context.inputs),
            output_schema=node.output_schema if isinstance(node.output_schema, dict) else {},
            toolset=node.toolset,
            policy=policy,
            verifier=self.verifier,
        )
        node_events = (
            _NodeEventSink(self.events, node.id) if self.events is not None else None
        )
        result = AgentKernel(
            self.llm,
            self.tools,
            state,
            events=node_events,
            should_stop=self.should_stop,
            checkpoints=self.checkpoints,
        ).run(task)
        return NodeResult(
            output=result.output,
            trace=result.history,
            usage=result.usage,
            cost_usd=result.cost_usd,
            stop_reason=result.stop_reason,
            checkpoint=result.metrics,
        )

"""Report as a fixed Workflow with per-node Kernels (Phase 3.4 / S13-S14).

source -> evidence -> map -> write
Each content node runs a Kernel loop and calls exactly one domain tool. The
report engine remains inside the tools so the workflow contracts are stable
while the internals are migrated.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from lit_agent.config import Settings
from lit_agent.kernel.events import EventSink, emit
from lit_agent.kernel.runtime import Kernel
from lit_agent.kernel.tools import KernelTools
from lit_agent.models.report import Report
from lit_agent.report.assemble import assemble_report, validate_report
from lit_agent.report.context import ReportContext, build_context
from lit_agent.report.synthesis import synthesize_all
from lit_agent.tools.spec import ToolRuntime, ToolSpec
from lit_agent.workflow.report_verifier import ReportVerifier
from lit_agent.workflow.runner import WorkflowRunner
from lit_agent.workflow.spec import NodeSpec, WorkflowSpec
from lit_agent.workflow.verifier import AgentVerifier

__all__ = ["ReportWorkflow"]


class ReportWorkflow:
    def __init__(
        self,
        settings: Settings,
        *,
        gateway: Any | None = None,
        event_sink: EventSink | None = None,
    ) -> None:
        self.settings = settings
        self.gateway = gateway
        self.event_sink = event_sink

    def run(
        self,
        *,
        run_id: str,
        topic_id: str,
        paper_ids: list[str] | None = None,
        limit: int = 100,
        focus_hint: str | None = None,
        title: str,
        period: str | None = None,
    ) -> tuple[Report, ReportContext]:
        language = self.settings.report.language
        holder: dict[str, Any] = {"context": None, "insights": None, "report": None, "paper_ids": list(paper_ids or [])}

        def tool_runtime(name: str, fn: Callable[..., Any], description: str) -> KernelTools:
            runtime = ToolRuntime()
            runtime.register(
                ToolSpec(
                    name=name,
                    description=description,
                    parameters={},
                    output_schema={},
                    timeout_s=600.0,
                    max_output_chars=10_000_000,
                ),
                fn,
            )
            return KernelTools(runtime)

        def kernel(tools: KernelTools, _tool: str, _node_id: str) -> Kernel:
            return Kernel(tools=tools, gateway=self.gateway, event_sink=self.event_sink)

        def completer_for(tool: str) -> Callable[..., dict[str, Any]]:
            def completer(history: list[dict[str, Any]], _goal: Any) -> dict[str, Any]:
                if not history:
                    return {"action": "tool", "tool": tool, "args": {}}
                return {"action": "final", "outputs": history[-1].get("output") or {}}

            return completer

        def load_scope(**_kwargs: Any) -> dict[str, Any]:
            from lit_agent.workflow.source import resolve_report_papers

            selected = resolve_report_papers(
                self.settings,
                topic_id,
                limit=limit,
                focus_hint=focus_hint,
                paper_ids=paper_ids,
            )
            holder["paper_ids"] = selected
            return {"paper_ids": selected, "count": len(selected), "topic_id": topic_id}

        def build_evidence(**_kwargs: Any) -> dict[str, Any]:
            context = build_context(
                self.settings, holder.get("paper_ids") or [], gateway=self.gateway
            )
            holder["context"] = context
            return {"context_id": "ctx", "papers": len(context.cards)}

        def build_map(**_kwargs: Any) -> dict[str, Any]:
            context = holder["context"]
            if not isinstance(context, ReportContext):
                raise RuntimeError("evidence context missing")
            insights = synthesize_all(
                context.directions,
                context.claim_set.claims,
                gateway=self.gateway if self.settings.report.synthesis else None,
                language=language,
                max_tokens=self.settings.report.max_tokens_synthesis,
            )
            holder["insights"] = insights
            return {"directions": len(context.directions), "insights": len(insights)}

        def build_report(**_kwargs: Any) -> dict[str, Any]:
            context = holder["context"]
            insights = holder["insights"]
            if not isinstance(context, ReportContext) or not isinstance(insights, list):
                raise RuntimeError("map output missing")
            llm_insights = sum(1 for item in insights if item.generated_by == "llm")
            fallback_count = len(insights) - llm_insights if self.settings.report.synthesis and self.gateway else 0
            if not self.settings.report.synthesis or self.gateway is None:
                generated_by = "template"
            elif fallback_count:
                generated_by = "hybrid"
            else:
                generated_by = "llm"
            by_paper = context.claim_set.by_paper()
            covered = sum(1 for card in context.cards if by_paper.get(card.paper_id))
            coverage = round(covered / len(context.cards), 4) if context.cards else 0.0
            report = assemble_report(
                run_id=run_id,
                topic_id=topic_id,
                title=title,
                period=period,
                context=context,
                insights=insights,
                language=language,
                generated_by=generated_by,
                fallback_count=fallback_count,
                coverage=coverage,
            )
            check = validate_report(report, language=language)
            if not check.ok:
                report = assemble_report(
                    run_id=run_id,
                    topic_id=topic_id,
                    title=title,
                    period=period,
                    context=context,
                    insights=[],
                    language=language,
                    generated_by="template",
                    fallback_count=len(insights),
                    coverage=0.0,
                )
                report = report.model_copy(update={"fallback_reason": "; ".join(check.errors[:3])})
            holder["report"] = report
            from contextlib import suppress

            from lit_agent.eval.metric_store import collect_workflow_points

            with suppress(Exception):
                collect_workflow_points(self.settings, run_id, context=context, report=report)
            return {"report_id": report.report_id, "sections": len(report.sections)}

        def node_kernel(tool: str, fn: Callable[..., Any], description: str, node_id: str) -> Kernel:
            return kernel(tool_runtime(tool, fn, description), tool, node_id)

        spec = WorkflowSpec(
            name="report",
            nodes=(
                NodeSpec(
                    id="source",
                    kind="agent",
                    goal="load the paper scope",
                    output_key="scope",
                    allowed_tools=("load_scope",),
                    postconditions=("count",),
                ),
                NodeSpec(
                    id="evidence",
                    kind="agent",
                    goal="build evidence context",
                    input_keys=("scope",),
                    output_key="evidence",
                    allowed_tools=("build_context",),
                    postconditions=("context_id",),
                ),
                NodeSpec(
                    id="map",
                    kind="agent",
                    goal="cluster and synthesize directions",
                    input_keys=("evidence",),
                    output_key="mapped",
                    allowed_tools=("synthesize",),
                    postconditions=("directions",),
                ),
                NodeSpec(
                    id="write",
                    kind="agent",
                    goal="assemble and validate the report",
                    input_keys=("mapped",),
                    output_key="bundle",
                    allowed_tools=("assemble",),
                    postconditions=("report_id",),
                ),
            ),
        )
        agent = AgentVerifier(self.gateway) if self.gateway is not None else None
        runner = WorkflowRunner(
            spec,
            verifier=ReportVerifier(agent=agent),
            kernels={
                "source": node_kernel("load_scope", load_scope, "load paper scope", "source"),
                "evidence": node_kernel("build_context", build_evidence, "build evidence context", "evidence"),
                "map": node_kernel("synthesize", build_map, "synthesize directions", "map"),
                "write": node_kernel("assemble", build_report, "assemble report", "write"),
            },
            completers={
                "source": completer_for("load_scope"),
                "evidence": completer_for("build_context"),
                "map": completer_for("synthesize"),
                "write": completer_for("assemble"),
            },
            event_sink=self.event_sink,
        )
        result = runner.run()
        report = holder.get("report")
        context = holder.get("context")
        if result.failed_node or not isinstance(report, Report) or not isinstance(context, ReportContext):
            raise RuntimeError(f"report workflow failed: {result.error}")
        for section in report.sections:
            emit(
                self.event_sink,
                "section.delta",
                node_id="write",
                section_id=section.id,
                title=section.title,
                chars=len(section.body),
            )
        return report, context

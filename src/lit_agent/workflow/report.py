"""Report as a fixed workflow (Phase 3.4 / S9 migration seam).

The first migration keeps the existing report engine as a kernel tool. The
outer node contract and kernel loop are new; the inner stages can be split in
later steps without changing the workflow API.
"""

from __future__ import annotations

from typing import Any

from lit_agent.config import Settings
from lit_agent.kernel.runtime import Kernel
from lit_agent.kernel.tools import KernelTools
from lit_agent.models.report import Report
from lit_agent.report.assemble import build_report_bundle
from lit_agent.report.context import ReportContext
from lit_agent.tools.spec import ToolRuntime, ToolSpec
from lit_agent.workflow.runner import WorkflowRunner
from lit_agent.workflow.spec import NodeSpec, WorkflowSpec

__all__ = ["ReportWorkflow"]


class ReportWorkflow:
    def __init__(self, settings: Settings, *, gateway: Any | None = None) -> None:
        self.settings = settings
        self.gateway = gateway

    def run(
        self,
        *,
        run_id: str,
        topic_id: str,
        paper_ids: list[str],
        title: str,
        period: str | None = None,
    ) -> tuple[Report, ReportContext]:
        runtime = ToolRuntime()

        def generate(**_kwargs: Any) -> dict[str, Any]:
            report, context = build_report_bundle(
                self.settings,
                run_id=run_id,
                topic_id=topic_id,
                paper_ids=paper_ids,
                title=title,
                period=period,
                gateway=self.gateway,
            )
            return {"report": report, "context": context}

        runtime.register(
            ToolSpec(
                name="generate_report",
                description="Generate the report and its evidence context",
                parameters={},
                output_schema={},
                timeout_s=600.0,
                max_output_chars=10_000_000,
            ),
            generate,
        )
        tools = KernelTools(runtime)

        def completer(history: list[dict[str, Any]], _goal: Any) -> dict[str, Any]:
            if not history:
                return {"action": "tool", "tool": "generate_report", "args": {}}
            output = history[-1].get("output")
            return {"action": "final", "outputs": output or {}}

        spec = WorkflowSpec(
            name="report",
            nodes=(
                NodeSpec(
                    id="generate",
                    kind="agent",
                    goal="generate a validated report",
                    output_key="bundle",
                    allowed_tools=("generate_report",),
                    postconditions=("report", "context"),
                    budget_usd=0.5,
                    timeout_s=600.0,
                ),
            ),
        )
        result = WorkflowRunner(
            spec,
            kernel=Kernel(tools=tools, gateway=self.gateway),
            completers={"generate": completer},
        ).run()
        bundle = result.artifacts.get("bundle")
        if result.failed_node or not isinstance(bundle, dict):
            raise RuntimeError(f"report workflow failed: {result.error}")
        report = bundle.get("report")
        context = bundle.get("context")
        if not isinstance(report, Report) or not isinstance(context, ReportContext):
            raise RuntimeError("report workflow produced invalid artifacts")
        return report, context

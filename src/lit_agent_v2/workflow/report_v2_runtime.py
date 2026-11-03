"""Composition for the report v2 workflow."""

from __future__ import annotations

from typing import Any

from lit_agent_v2.tools.general import build_general_tools
from lit_agent_v2.tools.packs.claims import build_claim_tools
from lit_agent_v2.tools.packs.corpus import build_corpus_tools
from lit_agent_v2.tools.packs.report import build_report_tools
from lit_agent_v2.tools.packs.report_v2 import build_report_v2_tools
from lit_agent_v2.tools.packs.source import build_source_tools
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.tools.runtime import ToolRuntime
from lit_agent_v2.workflow.report_v2 import report_v2_toolsets

__all__ = ["build_report_v2_runtime"]


def build_report_v2_runtime(llm: Any) -> ToolRuntime:
    registry = ToolRegistry(
        build_general_tools()
        + build_corpus_tools()
        + build_claim_tools()
        + build_source_tools()
        + build_report_tools(llm)
        + build_report_v2_tools(llm)
    )
    return ToolRuntime(
        registry,
        toolsets=report_v2_toolsets(),
        default_toolset=None,
    )

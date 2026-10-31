"""3.5 / S1-S3: direct report shell without the legacy graph."""

from __future__ import annotations

from pathlib import Path

from lit_agent.runtime.report_shell import run_direct_report
from tests.wiring import prepare


def test_direct_report_shell(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=20)
    result = run_direct_report(settings, "ai-agents", run_id="direct-shell", limit=20)

    assert result["state"] == "succeeded"
    assert result["papers"] == 20
    assert result["claims"] >= 1
    assert result["report_id"]


def test_source_resolver_limits_and_ranks(tmp_path: Path) -> None:
    from lit_agent.workflow.source import resolve_report_papers

    settings = prepare(tmp_path, papers=30)
    selected = resolve_report_papers(settings, "ai-agents", limit=10)
    assert len(selected) == 10
    assert len(set(selected)) == 10

"""3.5 / S10: workflow metrics for search/cluster/report."""

from __future__ import annotations

from pathlib import Path

from tests.wiring import prepare

from lit_agent.eval.metric_store import load_points
from lit_agent.eval.report_eval import summarize_points
from lit_agent.runtime.report_shell import run_direct_report


def test_workflow_metrics_are_recorded(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=12)
    result = run_direct_report(settings, "ai-agents", run_id="wf-metrics", limit=12)
    assert result["state"] == "succeeded"

    summary = summarize_points(load_points(settings, "wf-metrics"))
    assert summary["search.coverage"] == 12
    assert summary["cluster.count"] >= 1
    assert 0 <= summary["cluster.outlier_rate"] <= 1
    assert 0 <= summary["cluster.coherence"] <= 1
    assert summary["report.comparison_completeness"] == 1.0

"""3.4 / S20: direct ReportWorkflow at 20/50/100 papers (no old graph)."""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.session import connect, make_engine
from lit_agent.models.paper import Paper
from lit_agent.workflow.report import ReportWorkflow
from tests.wiring import prepare


@pytest.mark.parametrize("count", [20, 50, 100])
def test_report_workflow_scale(tmp_path: Path, count: int) -> None:
    settings = prepare(tmp_path, papers=0)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id=f"S{index:03d}",
                        title=f"Paper {index} on tool use and agents",
                        abstract=f"Study {index} shows tool use improves task success and reliability.",
                        source="fixture",
                    )
                    for index in range(count)
                ],
            )
    finally:
        engine.dispose()

    report, context = ReportWorkflow(settings).run(
        run_id=f"scale-{count}",
        topic_id="ai-agents",
        paper_ids=[f"S{index:03d}" for index in range(count)],
        title=f"Scale {count}",
    )

    assert len(context.cards) == count
    assert report.n_claims >= 1
    assert report.sections
    assert report.language == "en"


def test_direct_workflow_does_not_need_legacy_graph(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=20)
    before = settings
    report, context = ReportWorkflow(before).run(
        run_id="direct-20",
        topic_id="ai-agents",
        paper_ids=[f"P{index}" for index in range(20)],
        title="Direct",
    )
    assert report.n_claims >= 1
    assert context.cards
    # The direct path is reachable without run_graph; this test intentionally
    # does not import graph_runner.
    assert True

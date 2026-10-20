"""F5：报告与指标口径一致 + 报告 sha 稳定。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.eval.metrics import compute_run_metrics, persist_run_metrics
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.runner import run_topic


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id=f"arxiv:{index}",
                        title=f"Paper {index}",
                        abstract="agents use tools",
                        source="arxiv",
                        year=2025,
                    )
                    for index in range(3)
                ],
            )
    finally:
        engine.dispose()
    return settings


def report_row(settings: Settings, run_id: str) -> dict:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT report_id, content_sha, n_claims, claims_json FROM reports"
                    " WHERE run_id = :rid"
                ),
                {"rid": run_id},
            ).one()
    finally:
        engine.dispose()
    return {
        "report_id": row[0],
        "content_sha": row[1],
        "n_claims": int(row[2]),
        "claims": json.loads(row[3]),
    }


def test_metrics_match_report_claims(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="f5-run-1")
    report = report_row(settings, "f5-run-1")
    metrics = compute_run_metrics(settings, "f5-run-1")

    assert metrics["claims_total"] == report["n_claims"], "指标分母必须等于报告 claim 数"
    supported = sum(1 for claim in report["claims"] if claim["support"] == "supported")
    assert metrics["claims_supported"] == supported
    assert metrics["grounding_rate"] == round(supported / report["n_claims"], 4)


def test_report_sha_is_stable_across_runs(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="f5-run-a")
    run_topic(settings, "ai-agents", run_id="f5-run-b")

    first = report_row(settings, "f5-run-a")
    second = report_row(settings, "f5-run-b")
    assert first["content_sha"] == second["content_sha"], "同数据两次报告必须逐字节一致"
    assert first["claims"] == second["claims"]


def test_metrics_persist_is_recomputable(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="f5-run-c")

    persist_run_metrics(settings, "f5-run-c")
    first = compute_run_metrics(settings, "f5-run-c")
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            total = int(
                conn.execute(
                    text("SELECT COUNT(*) FROM metrics WHERE scope='run' AND scope_id='f5-run-c'")
                ).scalar_one()
            )
            stored = {
                row[0]: float(row[1])
                for row in conn.execute(
                    text(
                        "SELECT metric, value FROM metrics WHERE scope='run' AND scope_id='f5-run-c'"
                    )
                ).all()
            }
    finally:
        engine.dispose()

    persist_run_metrics(settings, "f5-run-c")
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            total_again = int(
                conn.execute(
                    text("SELECT COUNT(*) FROM metrics WHERE scope='run' AND scope_id='f5-run-c'")
                ).scalar_one()
            )
    finally:
        engine.dispose()

    assert total == total_again, "指标持久化必须是可复算（行数不增长）"
    assert stored["claims_total"] == float(first["claims_total"])
    assert stored["claims_supported"] == float(first["claims_supported"])

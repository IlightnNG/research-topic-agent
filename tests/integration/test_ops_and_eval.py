"""Step 1.17 调度/运维 + Step 1.18 指标（全离线）。"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from lit_agent.config import SchedulerSettings, Settings, StorageSettings
from lit_agent.db.repo import claims as claim_repo
from lit_agent.db.repo import llm_calls as llm_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.eval.export import export_metrics
from lit_agent.eval.metrics import compute_run_metrics, persist_run_metrics
from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, Support
from lit_agent.models.topic import Topic
from lit_agent.runtime.runner import run_topic
from lit_agent.runtime.scheduler import build_scheduler, cron_kwargs, list_jobs, run_once


def prepare(tmp_path: Path, *, enabled: bool = False) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        scheduler=SchedulerSettings(enabled=enabled),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="llm agents"))
    finally:
        engine.dispose()
    return settings


# --------------------------------------------------------------------------- #
# 1.17 scheduler
# --------------------------------------------------------------------------- #
def test_disabled_scheduler_registers_no_jobs(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    scheduler = build_scheduler(settings)
    assert list_jobs(scheduler) == []


def test_enabled_scheduler_registers_weekly_job(tmp_path: Path) -> None:
    settings = prepare(tmp_path, enabled=True)
    jobs = list_jobs(build_scheduler(settings))
    assert [job["id"] for job in jobs] == ["weekly"]


def test_cron_kwargs_parsing() -> None:
    assert cron_kwargs("0 3 * * 1") == {
        "minute": "0",
        "hour": "3",
        "day": "*",
        "month": "*",
        "day_of_week": "1",
    }


def test_run_once_marks_trigger_as_schedule(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = run_once(settings, "ai-agents")
    assert result["results"]["ai-agents"]["state"] == "succeeded"

    run_id = result["results"]["ai-agents"]["run_id"]
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            trigger = conn.execute(
                text("SELECT trigger FROM runs WHERE id = :rid"), {"rid": run_id}
            ).scalar_one()
    finally:
        engine.dispose()
    assert trigger == "schedule"


# --------------------------------------------------------------------------- #
# 1.18 metrics
# --------------------------------------------------------------------------- #
def test_metrics_are_none_when_denominator_is_zero(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="run-m0")

    metrics = compute_run_metrics(settings, "run-m0")
    assert metrics["claims"] == 0
    assert metrics["grounding_rate"] is None, "算不出来必须是 None，不是 0.0"


def test_metrics_computed_from_claims_and_calls(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="run-m1")

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            supported = Claim(
                text="agents plan",
                support=Support.SUPPORTED,
                citations=[Citation(paper_id="W1")],
            )
            unsupported = Claim(text="unproven", support=Support.UNSUPPORTED)
            claim_repo.insert_ignore_many(conn, "run-m1", [supported, unsupported])
            for claim in (supported, unsupported):
                digest = claim_repo.text_sha(claim.text)
                claim_repo.insert_citations_many(
                    conn, f"run-m1:{digest[:12]}", [("W1", None, "snippet", 0.9)]
                ) if claim is supported else None
            llm_repo.record(
                conn,
                run_id="run-m1",
                agent="reporter",
                provider="deepseek",
                model="deepseek-flash",
                route_reason="sensitivity:strict",
                request_sha="sha-m1",
                req_tokens=100,
                resp_tokens=20,
                cost=0.003,
            )
    finally:
        engine.dispose()

    metrics = compute_run_metrics(settings, "run-m1")
    assert metrics["claims"] == 2
    assert metrics["grounding_rate"] == 0.5
    assert metrics["hallucination_rate"] == 0.5
    assert metrics["citation_coverage"] == 0.5
    assert metrics["cost_usd"] == 0.003


def test_persist_run_metrics_is_idempotent(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="run-m2")

    persist_run_metrics(settings, "run-m2")
    persist_run_metrics(settings, "run-m2")

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text("SELECT COUNT(*) FROM metrics WHERE scope='run' AND scope_id='run-m2'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert int(rows) > 0


def test_export_metrics_formats(tmp_path: Path) -> None:
    rows = [compute_run_metrics(prepare(tmp_path), "run-none")]
    for name in ("m.json", "m.csv", "m.md"):
        path = export_metrics(rows, tmp_path / name)
        assert path.exists() and path.stat().st_size > 0
    assert "| scope |" in (tmp_path / "m.md").read_text(encoding="utf-8")

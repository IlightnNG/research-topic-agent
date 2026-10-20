"""批次 1（B/C/D/E 后端部分）与批次 2（focus_hint 生效）的回归测试。"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import text

from lit_agent.api.app import create_app
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.paper import Paper
from lit_agent.models.run import RunState
from lit_agent.models.topic import Topic
from lit_agent.runtime import control, jobs
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
                        paper_id="arxiv:tool",
                        title="Tool use in language agents",
                        abstract="agents call tools to act",
                        source="arxiv",
                        year=2025,
                    ),
                    Paper(
                        paper_id="arxiv:diff",
                        title="Diffusion models for protein design",
                        abstract="diffusion sampling for proteins",
                        source="arxiv",
                        year=2025,
                    ),
                ],
            )
    finally:
        engine.dispose()
    return settings


def report_of(settings: Settings, run_id: str) -> dict:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text("SELECT content_sha, claims_json, degraded FROM reports WHERE run_id = :r"),
                {"r": run_id},
            ).one()
    finally:
        engine.dispose()
    return {
        "sha": row[0],
        "claims": json.loads(row[1]),
        "degraded": bool(row[2]),
    }


# --------------------------------------------------------------------------- #
# 批次 1
# --------------------------------------------------------------------------- #
def test_async_202_run_is_queryable_immediately(tmp_path: Path) -> None:
    """B：202 返回时 run 行必须已存在（不能出现"幽灵 run"）。"""
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        started = client.post(
            "/api/topics/ai-agents/run", json={"run_id": "b-202", "wait": False}
        )
        assert started.status_code == 202
        immediate = client.get("/api/runs/b-202")
        assert immediate.status_code == 200, "202 之后立刻查询必须命中"
        assert immediate.json()["state"] in {"queued", "running", "succeeded"}


def test_async_lock_conflict_returns_409_not_202(tmp_path: Path) -> None:
    """B：锁冲突在请求线程内判定，返回 409，而不是先 202 再消失。"""
    settings = prepare(tmp_path)
    jobs.start(settings, "ai-agents", run_id="holder")
    try:
        with TestClient(create_app(settings)) as client:
            response = client.post(
                "/api/topics/ai-agents/run", json={"run_id": "blocked", "wait": False}
            )
        assert response.status_code == 409
        assert response.json()["code"] == "E_LOCK_HELD"
    finally:
        jobs.finish(settings, "holder", state=RunState.ABORTED)


def test_abort_unknown_run_is_404(tmp_path: Path) -> None:
    """D：中止不存在的 run → 404。"""
    settings = prepare(tmp_path)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/runs/nope/abort")
    assert response.status_code == 404
    assert response.json()["code"] == "E_NOT_FOUND"


def test_abort_flag_is_cleared_after_run(tmp_path: Path) -> None:
    """D：abort 标记必须在 finally 清理，否则集合只增不减。"""
    settings = prepare(tmp_path)
    control.request_abort("d-clean")
    result = run_topic(settings, "ai-agents", run_id="d-clean")
    assert result["state"] == "failed"
    assert result["error_code"] == "E_RUN_ABORTED"
    assert control.is_aborted("d-clean") is False, "标记应已清理"


# --------------------------------------------------------------------------- #
# 批次 2
# --------------------------------------------------------------------------- #
def test_focus_hint_filters_evidence_and_changes_report(tmp_path: Path) -> None:
    """A：不同 focus_hint 必须得到不同证据集与不同 content_sha。"""
    settings = prepare(tmp_path)
    run_topic(settings, "ai-agents", run_id="a-all")
    run_topic(settings, "ai-agents", run_id="a-diffusion", focus_hint="diffusion proteins")

    everything = report_of(settings, "a-all")
    focused = report_of(settings, "a-diffusion")

    assert len(everything["claims"]) == 2
    assert len(focused["claims"]) == 1, "hint 应把证据收窄到 1 条"
    assert everything["sha"] != focused["sha"], "hint 不同 → 报告内容必须不同"
    assert "Diffusion" in focused["claims"][0]["text"]


def test_focus_hint_without_match_degrades(tmp_path: Path) -> None:
    """A：hint 完全不匹配 → 0 证据 + 显式 degraded（不伪造）。"""
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="a-nomatch", focus_hint="quantum chromodynamics")
    assert result["state"] == "succeeded"
    assert result["stages"]["report"]["artifacts"]["cards"] == 0

    report = report_of(settings, "a-nomatch")
    assert report["degraded"] is True
    assert len(report["claims"]) == 1
    assert report["claims"][0]["support"] == "unsupported"

"""D8：LLM 摘要分支（离线，注入 completer）+ 降级路径。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime import runner
from lit_agent.runtime.runner import run_topic


def prepare(tmp_path: Path, *, papers: int = 2) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
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
                    for index in range(papers)
                ],
            )
    finally:
        engine.dispose()
    return settings


def _fake(monkeypatch: pytest.MonkeyPatch, completer) -> None:
    monkeypatch.setattr(runner, "_LLM_COMPLETER", completer)


def test_llm_summary_is_added_and_metered(tmp_path: Path, monkeypatch) -> None:
    calls: list[dict] = []

    def completer(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {"message": {"content": "Three sentence summary."}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "cost": 0.004},
        }

    _fake(monkeypatch, completer)
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="run-llm")
    assert result["state"] == "succeeded"
    assert len(calls) == 1, "有 completer 时应只调用一次摘要"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(text("SELECT content_md FROM reports WHERE run_id='run-llm'")).one()
            calls_rows = conn.execute(
                text("SELECT cost, cost_estimated FROM llm_calls WHERE run_id='run-llm'")
            ).all()
    finally:
        engine.dispose()

    assert "## Summary (LLM)" in row[0]
    assert "Three sentence summary." in row[0]
    assert calls_rows and calls_rows[0][0] == pytest.approx(0.004)
    assert result["budget"]["used_usd"] == pytest.approx(0.004), "成本必须计入同一个 RunBudget"


def test_llm_failure_falls_back_to_deterministic_report(tmp_path: Path, monkeypatch) -> None:
    def completer(**kwargs):
        raise RuntimeError("provider down")

    _fake(monkeypatch, completer)
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="run-llm-fail")

    assert result["state"] == "succeeded", "摘要失败不得让 run 失败"
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT content_md, claims_json, degraded FROM reports WHERE run_id='run-llm-fail'"
                )
            ).one()
    finally:
        engine.dispose()
    assert "## Summary (LLM)" not in row[0]
    assert json.loads(row[1]), "报告仍要有 claims"
    assert row[2] in (0, False)


def test_no_key_no_completer_skips_llm(tmp_path: Path, monkeypatch) -> None:
    _fake(monkeypatch, None)
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="run-no-llm")
    assert result["state"] == "succeeded"
    assert result["budget"]["used_usd"] == 0.0

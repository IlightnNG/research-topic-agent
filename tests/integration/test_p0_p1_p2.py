"""P0/P1/P2 验收：真实阶段链、预算统一、工具超时、报告与事件同事务。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import E_BUDGET_COST, E_SRC_TIMEOUT, LitError
from lit_agent.gateway.llm import LLMGateway
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.budget import RunBudget
from lit_agent.runtime.runner import run_topic
from lit_agent.tools.registry import Tool


def prepare(tmp_path: Path, *, papers: int = 0) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
            if papers:
                paper_repo.upsert_many(
                    conn,
                    [
                        Paper(
                            paper_id=f"10.1000/p{index}",
                            title=f"Paper {index}",
                            abstract=f"abstract of paper {index} about agents",
                            source="openalex",
                            year=2025,
                        )
                        for index in range(papers)
                    ],
                )
    finally:
        engine.dispose()
    return settings


def test_real_stages_ingest_curate_report(tmp_path: Path) -> None:
    """P0-1：真实主干能跑完，并把库里的论文变成带引用的报告。"""
    settings = prepare(tmp_path, papers=2)
    result = run_topic(settings, "ai-agents", run_id="run-real")

    assert result["state"] == "succeeded"
    stages = result["stages"]
    assert list(stages) == ["intake", "ingest", "curate", "report"]
    # 没配 selector → ingest 显式降级跳过（不是失败）
    assert stages["ingest"]["artifacts"]["skipped"] == "E_SRC_NO_SELECTOR"
    assert stages["curate"]["artifacts"]["unique"] == 2

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT content_md, claims_json, degraded FROM reports WHERE run_id='run-real'"
                )
            ).first()
    finally:
        engine.dispose()
    assert row is not None
    claims = json.loads(row[1])
    assert len(claims) == 2, "两篇论文 → 两条 claim"
    assert all(claim["citations"] for claim in claims), "每条 claim 必须带引用"
    assert all(claim["support"] == "supported" for claim in claims)
    assert row[2] in (0, False), "有证据时不得标 degraded"


def test_dedup_does_not_merge_version_lookalikes(tmp_path: Path) -> None:
    """回归：标题只差数字的论文不得被合并（GPT-3 vs GPT-4 / Paper 0 vs Paper 1）。"""
    from lit_agent.sources.dedup import run_dedup

    settings = prepare(tmp_path, papers=2)  # "Paper 0" / "Paper 1"
    result = run_dedup(settings)
    assert result["merged_pairs"] == 0, "数字不同的标题不是版本副本"
    assert result["unique"] == 2


def test_run_without_papers_is_degraded_not_fake(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    result = run_topic(settings, "ai-agents", run_id="run-empty")
    assert result["state"] == "succeeded"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text("SELECT claims_json, degraded FROM reports WHERE run_id='run-empty'")
            ).first()
            event_types = [
                item[0]
                for item in conn.execute(
                    text("SELECT type FROM run_events WHERE run_id='run-empty' ORDER BY seq")
                ).all()
            ]
    finally:
        engine.dispose()
    claims = json.loads(row[0])
    assert len(claims) == 1 and claims[0]["support"] == "unsupported"
    assert row[1] in (1, True), "无证据必须显式 degraded"
    assert event_types.count("report_written") == 1, "报告事件只能出现一次（同事务写入）"


def test_run_budget_unifies_with_gateway(tmp_path: Path) -> None:
    """P0-2：同一个 RunBudget 既是 run 预算又是 LLM 预算。"""
    settings = prepare(tmp_path)
    budget = RunBudget(limit_usd=0.01)
    budget.add(cost_usd=0.05)

    gateway = LLMGateway(settings, completer=lambda **_: {"choices": []}, budget=budget)
    with pytest.raises(LitError) as excinfo:
        gateway.chat([{"role": "user", "content": "hi"}])
    assert excinfo.value.code == E_BUDGET_COST


def test_tool_timeout_becomes_readable_error(tmp_path: Path) -> None:
    """P2：工具超时 → ToolResult(E_SRC_TIMEOUT)，不挂死调用方。"""
    import time

    def slow(**_: object) -> str:
        time.sleep(0.3)
        return "late"

    tool = Tool(name="slow", run=slow, timeout_s=0.05)
    result = tool()
    assert result.ok is False
    assert result.error_code == E_SRC_TIMEOUT
    assert result.meta["timeout_s"] == 0.05

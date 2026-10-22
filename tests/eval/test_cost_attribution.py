"""S13 验收：成本归因到 agent 维度。

不依赖真实 LLM：直接写两条 `llm_calls`（带 agent/cost），断言
`compute_run_metrics` 的 `cost_by_agent` / `calls_by_agent` 与落库的 `scope='agent'` 行。
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.eval.metrics import compute_run_metrics, persist_run_metrics
from lit_agent.models.topic import Topic
from lit_agent.runtime import jobs

INSERT = text(
    "INSERT INTO llm_calls(ts, run_id, agent, provider, model, request_sha, cache_hit,"
    " req_tokens, resp_tokens, cost, cost_estimated, latency_ms, degraded, ok)"
    " VALUES (:ts, 'cost-run', :agent, 'test', 'test', :sha, 0, 10, 5, :cost, 0, 12, 0, 1)"
)


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
        jobs.start(settings, "ai-agents", run_id="cost-run", engine=engine)
        with connect(engine, immediate=True) as conn:
            conn.execute(
                INSERT,
                {"ts": "2026-10-21T00:00:00Z", "agent": "analyst", "sha": "s1", "cost": 0.25},
            )
            conn.execute(
                INSERT,
                {"ts": "2026-10-21T00:00:01Z", "agent": "critic", "sha": "s2", "cost": 0.05},
            )
    finally:
        engine.dispose()
    return settings


def test_cost_is_attributed_per_agent(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    metrics = compute_run_metrics(settings, "cost-run")

    assert metrics["cost_by_agent"] == {"analyst": 0.25, "critic": 0.05}, metrics
    assert metrics["calls_by_agent"] == {"analyst": 1, "critic": 1}
    assert metrics["agents_used"] == 2
    assert abs(metrics["cost_usd"] - 0.30) < 1e-9

    persist_run_metrics(settings, "cost-run")

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT scope_id, value FROM metrics"
                    " WHERE scope = 'agent' AND scope_id LIKE 'cost-run:%'"
                )
            ).all()
    finally:
        engine.dispose()

    by_agent = {str(row[0]): float(row[1]) for row in rows}
    assert set(by_agent) == {"cost-run:analyst", "cost-run:critic"}, sorted(by_agent.items())
    assert abs(by_agent["cost-run:analyst"] - 0.25) < 1e-9
    assert abs(by_agent["cost-run:critic"] - 0.05) < 1e-9

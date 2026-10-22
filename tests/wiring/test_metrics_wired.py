"""S1 接线测试③：指标必须是 run 口径、落库、可被 API 读取（S5/S6 修复；xfail）。

判据：同话题跑两次（各一篇不同论文）→ 两个 run 的 claims_total 各自为 1；
`metrics` 表有 scope='run' 行；`GET /api/runs/{id}/metrics` 返回一致。
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from lit_agent.api.app import create_app
from lit_agent.db.session import connect, make_engine
from lit_agent.runtime.graph_runner import run_graph
from tests.wiring import prepare


@pytest.mark.xfail(strict=True, reason="S5/S6：run 口径与落库尚未接线")
def test_metrics_are_run_scoped_and_persisted(tmp_path: Path) -> None:
    settings = prepare(tmp_path, papers=2)
    run_graph(settings, "ai-agents", run_id="m1")
    run_graph(settings, "ai-agents", run_id="m2")

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT scope_id, metric, value FROM metrics"
                    " WHERE scope='run' AND metric='claims_total'"
                )
            ).all()
    finally:
        engine.dispose()

    by_run = {str(row[0]): float(row[2]) for row in rows}
    assert by_run.get("m1") == 1.0, by_run
    assert by_run.get("m2") == 1.0, by_run

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/runs/m1/metrics")
    assert response.status_code == 200, response.text
    assert float(response.json()["claims_total"]) == 1.0

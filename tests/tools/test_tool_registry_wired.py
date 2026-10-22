"""S10 验收：工具协议闭环（注册 / 调用 / 事件 / 超时 / 幂等）。"""

from __future__ import annotations

from pathlib import Path

from tests.wiring import fetch_events, prepare

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.models.topic import Topic
from lit_agent.runtime import jobs
from lit_agent.runtime.events import SqliteEventLog
from lit_agent.runtime.graph_runner import run_graph
from lit_agent.tools.registry import Tool, ToolRegistry, default_registry


def test_default_registry_has_paper_pdf() -> None:
    registry = default_registry()
    assert "paper_pdf" in registry.list_tools()


def test_tool_call_emits_event_and_is_idempotent(tmp_path: Path) -> None:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
        jobs.start(settings, "ai-agents", run_id="tool-run", engine=engine)
        log = SqliteEventLog(engine, "tool-run")
        registry = default_registry()

        body = "Sentence about agents. " * 300
        first = registry.call("paper_pdf", log=log, paper_id="P1", text=body, budget_tokens=64)
        assert first.ok is True
        chunks = first.output["hashes"]

        second = registry.call(
            "paper_pdf",
            log=log,
            paper_id="P1",
            text=body,
            budget_tokens=64,
            known_hashes=set(chunks),
        )
        assert second.output["new_chunks"] == 0

        jobs.finish(
            settings,
            "tool-run",
            state=__import__("lit_agent.models.run", fromlist=["RunState"]).RunState.ABORTED,
            engine=engine,
        )
    finally:
        engine.dispose()

    events = fetch_events(settings, "tool-run")
    calls = [event for event in events if event["type"] == "tool_call"]
    assert len(calls) == 2, calls
    assert all(event["payload"]["ok"] is True for event in calls)
    assert all("duration_ms" in event["payload"] for event in calls)


def test_tool_timeout_is_structured_error() -> None:
    import time

    registry = ToolRegistry()
    registry.register(
        Tool(name="slow", run=lambda **_: time.sleep(0.3), timeout_s=0.01)
    )
    result = registry.call("slow")
    assert result.ok is False
    assert result.error_code == "E_SRC_TIMEOUT"


def test_parse_uses_tool_only_when_enabled(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    cache = Path(settings.storage.data_root) / "pdf_texts"
    cache.mkdir(parents=True, exist_ok=True)
    (cache / "P0.txt").write_text("Agents use tools to improve success. " * 50, encoding="utf-8")

    run_graph(settings, "ai-agents", run_id="pdf-on", pdf_enabled=True, tools=default_registry())
    events = fetch_events(settings, "pdf-on")
    assert any(event["type"] == "tool_call" for event in events), "开关打开时必须走工具协议"

    run_graph(settings, "ai-agents", run_id="pdf-off")
    events_off = fetch_events(settings, "pdf-off")
    assert not any(event["type"] == "tool_call" for event in events_off)

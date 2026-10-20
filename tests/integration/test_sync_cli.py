"""F4：`sources sync` CLI 口径（--topic / --limit / 单源分派 / 错误码）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent import cli
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import E_SRC_NO_SELECTOR, LitError
from lit_agent.models.topic import Topic


def make_settings(tmp_path: Path) -> Settings:
    settings = Settings(
        storage=StorageSettings(data_root=str(tmp_path / "data")),
        logging=LoggingSettings(console=False),
    )
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            topic_repo.upsert(conn, Topic(id="ai-agents", name="AI", scope_statement="agents"))
    finally:
        engine.dispose()
    return settings


def test_sync_cli_passes_topic_and_limit(tmp_path: Path, monkeypatch, capsys) -> None:
    settings = make_settings(tmp_path)
    seen: dict[str, object] = {}

    def fake_sync(config, topic_id, *, limit=None):
        seen.update({"settings": config, "topic": topic_id, "limit": limit})
        return {"source": "arxiv", "topic_id": topic_id, "fetched": 20, "papers_new": 20}

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr("lit_agent.sources.sync.sync_topic", fake_sync)

    code = cli.main(["sources", "sync", "--topic", "ai-agents", "--limit", "20"])
    out = capsys.readouterr().out

    assert code == 0
    assert seen == {"settings": settings, "topic": "ai-agents", "limit": 20}
    assert "arxiv" in out, f"CLI 应打印含实际源的 JSON，实际输出={out!r}"


def test_sync_cli_requires_topic(capsys) -> None:
    with pytest.raises(SystemExit) as excinfo:
        cli.main(["sources", "sync"])
    assert excinfo.value.code != 0


def test_sync_without_selector_surfaces_actionable_code(tmp_path: Path, monkeypatch) -> None:
    settings = make_settings(tmp_path)

    def no_selector(config, topic_id, *, limit=None):
        raise LitError(E_SRC_NO_SELECTOR, f"topic {topic_id} 没有配置任何源 selector")

    monkeypatch.setattr(cli, "load_settings", lambda: settings)
    monkeypatch.setattr("lit_agent.sources.sync.sync_topic", no_selector)

    code = cli.main(["sources", "sync", "--topic", "ai-agents"])
    assert code != 0, "无 selector 必须以非零退出（不能静默成功）"

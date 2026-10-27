"""3.2 / S1 + S2：报告配置、迁移、PaperCard 构建与缓存。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from lit_agent.config import load_settings
from lit_agent.report.cards import CARD_VERSION, build_card, get_or_build_card, quote_ok, source_sha


class FakeGateway:
    def __init__(self, payload: dict, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail
        self.calls = 0

    def chat_json(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        self.calls += 1
        if self.fail:
            raise RuntimeError("llm down")
        return self.payload, None


PAPER = {
    "paper_id": "P0",
    "title": "Paper 0",
    "abstract": "tool use improves task success and reliability of LLM agents",
    "source": "arxiv",
    "year": 2026,
    "authors": [],
}


def test_report_settings_defaults() -> None:
    settings = load_settings(environ={}, dotenv_path=Path("none.env"))
    assert settings.report.language == "en"
    assert settings.report.synthesis is True
    assert settings.report.max_claims_per_paper == 3


def test_report_settings_env_override() -> None:
    settings = load_settings(
        environ={
            "LIT_AGENT_REPORT__SYNTHESIS": "false",
            "LIT_AGENT_REPORT__TOKEN_BUDGET": "80000",
            "LIT_AGENT_REPORT__LANGUAGE": "zh",
        },
        dotenv_path=Path("none.env"),
    )
    assert settings.report.synthesis is False
    assert settings.report.token_budget == 80000
    assert settings.report.language == "zh"


def test_migration_creates_report_tables(tmp_path: Path) -> None:
    from tests.wiring import prepare

    settings = prepare(tmp_path)
    conn = sqlite3.connect(settings.storage.sqlite_file)
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"paper_cards", "report_steps"} <= tables
    report_cols = {row[1] for row in conn.execute("PRAGMA table_info(reports)")}
    assert {"language", "generated_by", "word_count"} <= report_cols
    conn.close()


def test_deterministic_card_has_valid_quotes() -> None:
    settings = load_settings(environ={}, dotenv_path=Path("none.env"))
    card = build_card(settings, PAPER)

    assert card.paper_id == "P0"
    assert card.claims
    assert all(quote_ok(item["quote"], PAPER["abstract"]) for item in card.claims)
    assert card.evidence_level == "abstract_only"


def test_invalid_llm_quotes_are_dropped_but_fallback_kept() -> None:
    settings = load_settings(environ={}, dotenv_path=Path("none.env"))
    gateway = FakeGateway(
        {
            "problem": {"text": "bad", "quote": "not in the source"},
            "claims": [{"text": "bad", "quote": "also absent"}],
        }
    )
    card = build_card(settings, PAPER, gateway=gateway)

    assert card.problem is None
    assert card.meta["dropped_quotes"] >= 1
    assert card.claims  # 确定性兜底仍在


def test_llm_failure_falls_back() -> None:
    settings = load_settings(environ={}, dotenv_path=Path("none.env"))
    card = build_card(settings, PAPER, gateway=FakeGateway({}, fail=True))
    assert card.meta["llm_used"] is False
    assert card.claims


def test_cache_hit_skips_llm(tmp_path: Path) -> None:
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=1)
    first = get_or_build_card(settings, "P0")
    gateway = FakeGateway({}, fail=True)
    second = get_or_build_card(settings, "P0", gateway=gateway)

    assert second.to_dict() == first.to_dict()
    assert gateway.calls == 0


def test_cache_invalidated_by_content_change(tmp_path: Path) -> None:
    from sqlalchemy import text

    from lit_agent.db.session import connect, make_engine
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=1)
    get_or_build_card(settings, "P0")

    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text("UPDATE papers SET abstract = :a WHERE paper_id = 'P0'"),
                {"a": "a completely different abstract about retrieval"},
            )
    finally:
        engine.dispose()

    gateway = FakeGateway(
        {"problem": {"text": "retrieval", "quote": "a completely different abstract about retrieval"}}
    )
    card = get_or_build_card(settings, "P0", gateway=gateway)
    assert gateway.calls == 1
    assert card.problem is not None
    assert source_sha(card.title, "a completely different abstract about retrieval") != source_sha(
        card.title, PAPER["abstract"]
    )


def test_missing_text_is_marked() -> None:
    settings = load_settings(environ={}, dotenv_path=Path("none.env"))
    card = build_card(settings, {**PAPER, "abstract": "", "title": "Only a title"})
    assert card.evidence_level == "missing"
    assert card.claims == []
    assert CARD_VERSION >= 1

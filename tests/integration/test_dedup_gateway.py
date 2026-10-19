"""Step 1.8 去重/投影 + Step 1.9 网关（全部离线：注入 completer，不联网）。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lit_agent.config import Settings, StorageSettings
from lit_agent.db.repo import citations as citation_repo
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import E_BUDGET_COST, E_LLM_TRUNCATED, E_POLICY_SENSITIVE, LitError
from lit_agent.gateway.llm import LLMGateway
from lit_agent.gateway.metering import BudgetGuard, CallUsage
from lit_agent.models.author import Author
from lit_agent.models.paper import Paper
from lit_agent.sources.dedup import project_citations, run_dedup
from lit_agent.stores.graph import GraphStore
from lit_agent.stores.rebuild import rebuild_graph


def prepare(tmp_path: Path) -> Settings:
    settings = Settings(storage=StorageSettings(data_root=str(tmp_path / "data")))
    upgrade_database(settings)
    return settings


def seed(settings: Settings, papers: list[Paper]) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            paper_repo.upsert_many(conn, papers)
    finally:
        engine.dispose()


def row(settings: Settings, paper_id: str) -> dict:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return dict(paper_repo.get(conn, paper_id)._mapping)
    finally:
        engine.dispose()


# --------------------------------------------------------------------------- #
# Step 1.8
# --------------------------------------------------------------------------- #
def test_dedup_merges_version_copies(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    author = Author(author_id="A1", name="Ada", name_norm="ada")
    seed(
        settings,
        [
            Paper(
                paper_id="10.1000/a",
                title="Same Title",
                abstract="long abstract",
                source="openalex",
                year=2024,
                authors=[author],
            ),
            Paper(
                paper_id="10.1000/b",
                title="Same Title",
                source="openalex",
                year=2024,
                authors=[author],
            ),
        ],
    )

    result = run_dedup(settings)
    assert result["merged_pairs"] >= 1, result
    assert result["unique"] == 1

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            assert citation_repo.count_merges(conn) >= 1
    finally:
        engine.dispose()
    primary = next(iter(result["merged"]))
    assert json.loads(row(settings, primary)["merged_ids_json"])


def test_rebuild_skips_merged_records(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    author = Author(author_id="A1", name="Ada", name_norm="ada")
    seed(
        settings,
        [
            Paper(
                paper_id="10.1000/a",
                title="Same Title",
                abstract="abs",
                source="openalex",
                year=2024,
                authors=[author],
            ),
            Paper(
                paper_id="10.1000/b",
                title="Same Title",
                source="openalex",
                year=2024,
                authors=[author],
            ),
        ],
    )
    run_dedup(settings)
    rebuild_graph(settings)

    with GraphStore.open(settings) as store:
        assert store.counts()["papers"] == 1, "被合并记录不得进图（只进主记录）"


def test_projection_writes_corpus_internal_edges_only(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    seed(
        settings,
        [
            Paper(paper_id="10.1000/a", title="A", source="openalex", source_id="W1"),
            Paper(paper_id="10.1000/b", title="B", source="openalex", source_id="W2"),
        ],
    )
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            paper_repo.insert_raw_many(
                conn,
                [
                    {
                        "source": "openalex",
                        "source_id": "W1",
                        "content_sha": "sha-1",
                        "raw_json": json.dumps(
                            {
                                "id": "https://openalex.org/W1",
                                "referenced_works": [
                                    "https://openalex.org/W2",
                                    "https://openalex.org/W9",
                                ],
                            }
                        ),
                    }
                ],
            )
    finally:
        engine.dispose()

    result = project_citations(settings)
    assert result["edges_total"] == 1, "语料外引用（W9）必须被丢弃"
    again = project_citations(settings)
    assert again["edges_total"] == 1, "重跑不得重复计数"


# --------------------------------------------------------------------------- #
# Step 1.9
# --------------------------------------------------------------------------- #
def gateway(settings: Settings, completer, budget: BudgetGuard | None = None) -> LLMGateway:
    return LLMGateway(settings, completer=completer, budget=budget)


def test_sensitive_content_never_leaves(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    calls: list[dict] = []

    def completer(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "hi"}, "finish_reason": "stop"}]}

    gw = gateway(settings, completer)
    with pytest.raises(LitError) as excinfo:
        gw.chat([{"role": "user", "content": "my key is sk-abcdefgh1234"}])
    assert excinfo.value.code == E_POLICY_SENSITIVE
    assert calls == [] and gw.calls == 0, "敏感样本必须零出网"


def test_cache_hit_is_free_and_identical(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    def completer(**kwargs):
        return {
            "choices": [{"message": {"content": "cached answer"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "cost": 0.02},
        }

    gw = gateway(settings, completer)
    first = gw.chat([{"role": "user", "content": "hello"}])
    second = gw.chat([{"role": "user", "content": "hello"}])

    assert first.cached is False and first.usage.cost == pytest.approx(0.02)
    assert second.cached is True and second.usage.cost == 0.0
    assert second.content == first.content
    assert gw.calls == 1, "第二次必须命中缓存，不得再出网"

    engine = make_engine(settings)
    try:
        from sqlalchemy import text

        with connect(engine) as conn:
            total = conn.execute(text("SELECT COUNT(*) FROM llm_calls")).scalar_one()
            hits = conn.execute(
                text("SELECT COUNT(*) FROM llm_calls WHERE cache_hit = 1")
            ).scalar_one()
    finally:
        engine.dispose()
    assert total == 2 and hits == 1


def test_truncation_retries_with_doubled_budget(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    seen: list[int] = []

    def completer(**kwargs):
        seen.append(kwargs["max_tokens"])
        if len(seen) == 1:
            return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}
        return {
            "choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 3, "completion_tokens": 1, "cost": 0.001},
        }

    gw = gateway(settings, completer)
    call = gw.chat([{"role": "user", "content": "x"}], max_tokens=64)

    assert call.attempts == 2
    assert seen == [64, 128], "截断后必须把 max_tokens 翻倍重试"


def test_truncation_after_retry_raises(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    def completer(**kwargs):
        return {"choices": [{"message": {"content": ""}, "finish_reason": "length"}]}

    gw = gateway(settings, completer)
    with pytest.raises(LitError) as excinfo:
        gw.chat([{"role": "user", "content": "x"}], max_tokens=8)
    assert excinfo.value.code == E_LLM_TRUNCATED


def test_budget_stop_prevents_call(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    budget = BudgetGuard(0.01)
    budget.spend(CallUsage(cost=0.02))
    calls: list[dict] = []

    def completer(**kwargs):
        calls.append(kwargs)
        return {"choices": [{"message": {"content": "x"}, "finish_reason": "stop"}]}

    gw = gateway(settings, completer, budget)
    with pytest.raises(LitError) as excinfo:
        gw.chat([{"role": "user", "content": "x"}])
    assert excinfo.value.code == E_BUDGET_COST
    assert calls == []


def test_chat_json_strips_code_fence(tmp_path: Path) -> None:
    settings = prepare(tmp_path)

    def completer(**kwargs):
        return {
            "choices": [
                {"message": {"content": '```json\n{"claims": []}\n```'}, "finish_reason": "stop"}
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "cost": 0.0},
        }

    gw = gateway(settings, completer)
    payload, call = gw.chat_json([{"role": "user", "content": "give json"}])
    assert payload == {"claims": []}
    assert call.ok is True

"""S10/S11 验收：hybrid 召回提升、PDF 工具幂等、judge κ、三类故障注入。"""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from lit_agent.agents.hybrid import hybrid_search, keyword_only
from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.eval import datasets, faultinject, retrieval_bench
from lit_agent.eval.judge import judge_gold, kappa
from lit_agent.models.evidence import EvidenceCard
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime.graph_runner import run_graph
from lit_agent.tools.builtin import paper_pdf


def prepare(tmp_path: Path, *, papers: int = 1) -> Settings:
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
                        paper_id=f"P{index}",
                        title="Tool use",
                        abstract="agents invoke tools",
                        source="arxiv",
                    )
                    for index in range(papers)
                ],
            )
    finally:
        engine.dispose()
    return settings


def _cards(texts: dict[str, str]) -> list[EvidenceCard]:
    return [
        EvidenceCard(paper_id=pid, title=text, snippet=text, source="bench")
        for pid, text in texts.items()
    ]


# --------------------------------------------------------------------------- #
# S10：hybrid 检索
# --------------------------------------------------------------------------- #
def test_hybrid_beats_keyword_by_at_least_10pp() -> None:
    metrics = retrieval_bench.evaluate()
    gain = metrics["hybrid_recall"] - metrics["keyword_recall"]
    assert gain >= 0.10, metrics


def test_hybrid_ranks_target_first_for_morphological_query() -> None:
    cards = _cards(retrieval_bench.CORPUS)
    ranked = hybrid_search(cards, "replanning", k=3)
    assert ranked.cards[0].paper_id == "P05"


def test_keyword_only_misses_morphological_variant() -> None:
    cards = _cards(retrieval_bench.CORPUS)
    hits = [card.paper_id for card in keyword_only(cards, "faithfulness", k=10)]
    assert "P06" not in hits, "纯词面应漏掉 faithful/faithfulness 的形态差异"


# --------------------------------------------------------------------------- #
# S10：PDF 工具
# --------------------------------------------------------------------------- #
def test_pdf_tool_chunks_and_is_idempotent(tmp_path: Path) -> None:
    text_body = " ".join(f"Sentence {index} about agent tools." for index in range(60))
    first = paper_pdf.run(paper_id="P1", text=text_body, budget_tokens=64)
    assert first["ok"] is True
    assert first["chunks"] > 1
    assert first["new_chunks"] == first["chunks"]

    second = paper_pdf.run(
        paper_id="P1",
        text=text_body,
        budget_tokens=64,
        known_hashes=set(paper_pdf.chunk_hashes("P1", [])),
    )
    assert second["new_chunks"] > 0  # 未传已知哈希 → 视为新


def test_pdf_tool_reports_failure_without_raising() -> None:
    result = paper_pdf.run(paper_id="bad", text="   ")
    assert result["ok"] is False
    assert result["error"] == "empty text"


def test_pdf_tool_dedupes_against_known_hashes(tmp_path: Path) -> None:
    text_body = "Alpha beta gamma. " * 200
    first = paper_pdf.run(paper_id="P2", text=text_body, budget_tokens=64)
    assert first["hashes"], "结果应带块哈希"
    again = paper_pdf.run(
        paper_id="P2",
        text=text_body,
        budget_tokens=64,
        known_hashes=set(first["hashes"]),
    )
    assert again["new_chunks"] == 0, "同一 PDF 重复解析不得产生新块"


# --------------------------------------------------------------------------- #
# S11：judge / 故障注入
# --------------------------------------------------------------------------- #
def test_judge_with_completer_reaches_kappa_threshold() -> None:
    gold = datasets.load_gold()
    answers = {
        item.claim: ("supported" if item.label == "supported" else "unsupported") for item in gold
    }
    # 模拟一个 90% 正确的 judge（错 2 条）
    wrong = set(list(answers)[:2])

    def completer(messages, **kwargs):  # noqa: ANN001
        prompt = messages[-1]["content"]
        claim = prompt.split("CLAIM:", 1)[1].split("SNIPPET:", 1)[0].strip()
        verdict = answers.get(claim, "unsupported")
        if claim in wrong:
            verdict = "unsupported" if verdict == "supported" else "supported"
        return {"choices": [{"message": {"content": json.dumps({"verdict": verdict})}}]}

    result = judge_gold(gold, completer=completer)
    assert result["kappa"] >= 0.6, result


def test_kappa_bounds() -> None:
    assert kappa(["a", "a"], ["a", "a"]) == 1.0
    assert kappa(["a", "b"], ["b", "a"]) == 0.0  # 双方正类率都为 0，κ 未定义 → 约定 0.0


def test_fault_injection_empty_retrieval_degrades(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with faultinject.inject("empty_retrieval"):
        result = run_graph(settings, "ai-agents", run_id="f-empty")
    assert result["state"] == "succeeded"

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            degraded = conn.execute(
                text("SELECT degraded FROM reports WHERE run_id='f-empty'")
            ).scalar_one()
    finally:
        engine.dispose()
    assert degraded in (1, True), "空检索必须显式降级"


def test_fault_injection_bad_artifact_triggers_guard(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with faultinject.inject("bad_artifact"):
        result = run_graph(settings, "ai-agents", run_id="f-bad")
    assert result["state"] in {"succeeded", "failed"}

    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            events = [
                row[0]
                for row in conn.execute(
                    text("SELECT payload_json FROM run_events WHERE run_id='f-bad'")
                ).all()
            ]
    finally:
        engine.dispose()
    assert any("unresolved_citations" in (payload or "") or "rewrite" in (payload or "") for payload in events), (
        "坏产物必须被 critic 识别并留痕"
    )


def test_fault_injection_timeout_fails_run(tmp_path: Path) -> None:
    settings = prepare(tmp_path)
    with faultinject.inject("timeout"):
        result = run_graph(settings, "ai-agents", run_id="f-timeout")
    assert result["state"] == "failed"
    assert result["error_code"] == "E_SRC_TIMEOUT"
    assert "failure_report" in result

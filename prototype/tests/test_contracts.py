"""Step 0.2 契约单测：模型约束、事件日志语义、错误可预期性。

对照验收标准（docs/implementation/phase0-implementation-steps.md §2 Step 0.2）：
1. 连续 `emit` 3 条事件 → 文件 3 行且 `seq` 为 1/2/3；
2. 必填字段缺失/非法 → 抛结构化错误（消息含字段名），不打印堆栈；
3. 模型 JSON 往返一致。
"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from lit_agent_min.eventlog import EventLogError, JsonlEventLog, read_events
from lit_agent_min.models import (
    Author,
    Citation,
    Claim,
    Event,
    EventType,
    EvidenceCard,
    GuardAction,
    Paper,
    Severity,
    Support,
    Verdict,
)
from pydantic import ValidationError


def make_paper(**overrides: object) -> Paper:
    payload: dict[str, object] = {
        "paper_id": "W2963087533",
        "title": "ReAct: Synergizing Reasoning and Acting in Language Models",
        "abstract": "We explore the use of LLMs to generate reasoning traces and task actions.",
        "authors": [Author(author_id="A1", name="Shunyu Yao", name_norm="shunyu yao")],
        "venue": "ICLR",
        "year": 2023,
        "source": "openalex",
        "references": ["W123"],
        "oa_pdf_url": "https://example.org/paper.pdf",
    }
    payload.update(overrides)
    return Paper(**payload)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 模型约束
# --------------------------------------------------------------------------- #
def test_paper_json_round_trip() -> None:
    paper = make_paper()
    restored = Paper.model_validate_json(paper.model_dump_json())
    assert restored == paper
    assert restored.authors[0].name_norm == "shunyu yao"


def test_paper_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError) as excinfo:
        make_paper(canonical_id="typo")
    assert "canonical_id" in str(excinfo.value)  # 字段名必须出现在错误里


def test_paper_rejects_bad_values() -> None:
    with pytest.raises(ValidationError):
        make_paper(paper_id="")
    with pytest.raises(ValidationError):
        make_paper(paper_id="W 123")  # 不得含空白
    with pytest.raises(ValidationError):
        make_paper(year=1700)
    with pytest.raises(ValidationError):
        make_paper(year=2300)


def test_contract_models_are_frozen() -> None:
    paper = make_paper()
    with pytest.raises(ValidationError):
        paper.title = "mutated"  # type: ignore[misc]


def test_claim_requires_citation_unless_unverified() -> None:
    text = "ReAct interleaves reasoning traces with tool calls."
    with pytest.raises(ValidationError) as excinfo:
        Claim(text=text, support=Support.SUPPORTED)
    assert "citation" in str(excinfo.value)

    claim = Claim(text=text, support=Support.SUPPORTED, citations=[Citation(paper_id="W1")])
    assert claim.citations[0].paper_id == "W1"

    # 未核实断言允许无引用（但必须显式声明 unverified）
    assert Claim(text=text).support is Support.UNVERIFIED


def test_verdict_requires_reasons_on_failure() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Verdict(ok=False, code="E_GUARD_DRIFT")
    assert "reasons" in str(excinfo.value)

    verdict = Verdict(ok=True, code="E_GUARD_DRIFT", action=GuardAction.CONTINUE)
    assert verdict.severity is Severity.INFO  # 默认值
    failed = Verdict(
        ok=False,
        severity=Severity.WARNING,
        action=GuardAction.REPLAN,
        code="E_GUARD_DRIFT",
        reasons=["scope 相似度 0.42 < 0.45"],
    )
    assert failed.action is GuardAction.REPLAN


def test_evidence_card_to_citation_keeps_snippet() -> None:
    card = EvidenceCard(
        paper_id="W1", title="T", year=2024, snippet="…evidence…", source="openalex", score=0.87
    )
    citation = card.to_citation()
    assert citation.paper_id == "W1"
    assert citation.snippet == "…evidence…"


# --------------------------------------------------------------------------- #
# 事件
# --------------------------------------------------------------------------- #
def test_event_requires_timezone_aware_ts() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Event(run_id="r1", seq=1, ts=datetime(2026, 1, 1, 3, 0, 0), type=EventType.MESSAGE)
    assert "ts" in str(excinfo.value)

    event = Event(
        run_id="r1", seq=1, ts=datetime(2026, 1, 1, 3, 0, 0, tzinfo=UTC), type=EventType.MESSAGE
    )
    assert event.ts.utcoffset() == timedelta(0)


def test_event_rejects_non_json_payload() -> None:
    with pytest.raises(ValidationError) as excinfo:
        Event(
            run_id="r1",
            seq=1,
            ts=datetime.now(UTC),
            type=EventType.TOOL_CALL,
            payload={"bad": object()},
        )
    assert "payload" in str(excinfo.value)


def test_event_json_line_round_trip() -> None:
    event = Event(
        run_id="p0-s5-001",
        seq=3,
        ts=datetime(2026, 10, 5, 12, 0, tzinfo=UTC),
        type=EventType.LLM_CALL,
        stage="retrieve",
        agent="single",
        severity=Severity.INFO,
        payload={"provider": "deepseek", "tokens": 123, "nested": {"ok": True}},
    )
    line = event.to_json_line()
    assert "\n" not in line
    assert json.loads(line)["payload"]["nested"]["ok"] is True
    assert Event.from_json_line(line) == event


# --------------------------------------------------------------------------- #
# 事件日志（JSONL）
# --------------------------------------------------------------------------- #
def test_emit_three_events_writes_three_lines_with_seq_1_2_3(tmp_path: Path) -> None:
    """验收标准 1：3 条事件 → 3 行、seq = 1/2/3。"""
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path, run_id="p0-s5-001")

    for index in range(3):
        log.emit(EventType.PHASE_CHANGE, stage="retrieve", payload={"i": index})

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    assert [json.loads(line)["seq"] for line in lines] == [1, 2, 3]
    assert [event.seq for event in log.events()] == [1, 2, 3]
    assert log.seq == 3


def test_events_read_back_matches_emitted(tmp_path: Path) -> None:
    log = JsonlEventLog(tmp_path / "e.jsonl", run_id="r1")
    first = log.emit(EventType.MESSAGE, payload={"text": "hi"})
    second = log.emit(EventType.ERROR, severity=Severity.ERROR, payload={"code": "E_SRC_TIMEOUT"})
    assert log.events() == [first, second]
    assert log.events()[1].severity is Severity.ERROR


def test_seq_resumes_after_reopen(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path, run_id="r1")
    log.emit(EventType.MESSAGE)
    log.emit(EventType.MESSAGE)

    reopened = JsonlEventLog(path, run_id="r1")
    assert reopened.seq == 2
    assert reopened.emit(EventType.MESSAGE).seq == 3
    assert [event.seq for event in read_events(path)] == [1, 2, 3]


def test_seq_is_per_run_id(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    run_a = JsonlEventLog(path, run_id="A")
    run_b = JsonlEventLog(path, run_id="B")
    run_a.emit(EventType.MESSAGE)
    run_b.emit(EventType.MESSAGE)

    assert [event.seq for event in read_events(path, run_id="A")] == [1]
    assert [event.seq for event in read_events(path, run_id="B")] == [1]
    assert len(read_events(path)) == 2


def test_concurrent_emit_produces_unique_monotonic_seq(tmp_path: Path) -> None:
    log = JsonlEventLog(tmp_path / "events.jsonl", run_id="r1")
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda i: log.emit(EventType.METRIC, payload={"i": i}), range(50)))

    seqs = sorted(event.seq for event in log.events())
    assert seqs == list(range(1, 51))


def test_invalid_type_raises_structured_error(tmp_path: Path) -> None:
    """验收标准 2：非法/缺失字段 → 结构化错误（含字段名），不写半行。"""
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path, run_id="r1")

    with pytest.raises(EventLogError) as excinfo:
        log.emit("not_a_valid_type")
    assert "type" in str(excinfo.value)
    assert not path.exists() or path.read_text(encoding="utf-8") == ""


def test_failed_emit_does_not_write_partial_line(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    log = JsonlEventLog(path, run_id="r1")
    log.emit(EventType.MESSAGE)

    with pytest.raises(EventLogError) as excinfo:
        log.emit(EventType.TOOL_CALL, payload={"bad": object()})
    assert "payload" in str(excinfo.value)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1, "失败的事件不得留下半行"
    assert log.seq == 1, "失败的写入不得推进 seq"


def test_corrupt_line_reports_lineno(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    JsonlEventLog(path, run_id="r1").emit(EventType.MESSAGE)
    with path.open("a", encoding="utf-8") as handle:
        handle.write('{"run_id": "r1", broken}\n')

    with pytest.raises(EventLogError) as excinfo:
        read_events(path)
    assert "2" in str(excinfo.value)  # 行号


def test_read_events_missing_file_returns_empty(tmp_path: Path) -> None:
    assert read_events(tmp_path / "nope.jsonl") == []

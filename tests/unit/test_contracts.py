"""契约模型（Step 1.2 验收）：往返、约束、事件时序与幂等字段。"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from lit_agent.models import (
    AnalysisResult,
    Author,
    Citation,
    Claim,
    Event,
    EventType,
    EvidenceCard,
    GuardAction,
    GuardSeverity,
    Paper,
    ParseStatus,
    Report,
    ReportDraft,
    RetrievalResult,
    Run,
    RunContext,
    RunState,
    Severity,
    StageResult,
    Support,
    Topic,
    Verdict,
)


def paper(**overrides: object) -> Paper:
    base: dict[str, object] = {
        "paper_id": "10.1000/x",
        "title": "An Agent Survey",
        "source": "openalex",
    }
    base.update(overrides)
    return Paper(**base)  # type: ignore[arg-type]


def test_paper_roundtrip_keeps_merged_ids() -> None:
    original = paper(
        merged_ids=["W123", "arxiv:2401.1"], parse_status=ParseStatus.OK, cited_by_count=7
    )
    restored = Paper.model_validate_json(original.model_dump_json())
    assert restored == original
    assert restored.merged_ids == ["W123", "arxiv:2401.1"]
    assert restored.parse_status is ParseStatus.OK


def test_paper_rejects_whitespace_in_id() -> None:
    with pytest.raises(ValidationError):
        paper(paper_id="W 123")


def test_extra_fields_are_forbidden() -> None:
    with pytest.raises(ValidationError):
        paper(typo_field=1)


def test_evidence_card_makes_citation() -> None:
    card = EvidenceCard(paper_id="W1", title="T", snippet="s", source="openalex", score=0.5)
    citation = card.to_citation()
    assert citation == Citation(paper_id="W1", snippet="s")


def test_claim_requires_citations_when_decided() -> None:
    with pytest.raises(ValidationError):
        Claim(text="x", support=Support.SUPPORTED, citations=[])
    # 未核实 / 不可落地 允许无引用（必须能入库）
    assert Claim(text="x", support=Support.UNSUPPORTED).citations == []
    ok = Claim(text="x", support=Support.SUPPORTED, citations=[Citation(paper_id="W1")])
    assert ok.support is Support.SUPPORTED


def test_verdict_requires_reasons_when_failed() -> None:
    with pytest.raises(ValidationError):
        Verdict(ok=False, code="E_GUARD_DRIFT", reasons=[])
    verdict = Verdict(
        ok=False,
        severity=GuardSeverity.BLOCK,
        action=GuardAction.REPLAN,
        code="E_GUARD_DRIFT",
        reasons=["cosine 0.04 < block 0.0777"],
    )
    assert verdict.action is GuardAction.REPLAN


def test_guard_action_and_severity_vocabulary() -> None:
    assert {a.value for a in GuardAction} == {
        "continue",
        "retry",
        "degrade",
        "replan",
        "abort",
        "annotate",
    }
    assert {s.value for s in GuardSeverity} == {"info", "warn", "block"}


def make_event(**overrides: object) -> Event:
    base: dict[str, object] = {
        "run_id": "run-1",
        "seq": 1,
        "ts": datetime(2026, 10, 19, 3, 0, tzinfo=UTC),
        "type": EventType.PHASE_CHANGE,
        "payload": {"stage": "retrieval"},
    }
    base.update(overrides)
    return Event(**base)  # type: ignore[arg-type]


def test_event_requires_timezone() -> None:
    with pytest.raises(ValidationError):
        make_event(ts=datetime(2026, 10, 19, 3, 0))


def test_event_payload_must_be_json_serializable() -> None:
    with pytest.raises(ValidationError):
        make_event(payload={"bad": object()})


def test_event_dedupe_key_shape() -> None:
    assert (
        make_event(dedupe_key="retrieval:openalex:page:3").dedupe_key == "retrieval:openalex:page:3"
    )
    with pytest.raises(ValidationError):
        make_event(dedupe_key="no-colon")
    with pytest.raises(ValidationError):
        make_event(dedupe_key="   ")


def test_event_type_whitelist() -> None:
    with pytest.raises(ValidationError):
        make_event(type="bogus")


def test_event_json_line_roundtrip() -> None:
    event = make_event(type=EventType.METRIC, payload={"kind": "dedup_rate", "value": 0.19})
    line = event.to_json_line()
    assert "\n" not in line
    assert Event.from_json_line(line) == event


def test_event_from_bad_line_raises_value_error() -> None:
    with pytest.raises(ValueError):
        Event.from_json_line("{not json}")


def test_run_context_resources_are_not_serialized() -> None:
    ctx = RunContext(run_id="r1", topic_id="t1", resources={"session": object()})
    dumped = ctx.model_dump(mode="json")
    assert "resources" not in dumped
    assert ctx.model_dump_json()  # 不因不可序列化对象而失败


def test_stage_and_retrieval_results_roundtrip() -> None:
    result = StageResult(stage="retrieval", metrics={"papers_new": 3.0}, notes=["ok"])
    assert StageResult.model_validate_json(result.model_dump_json()) == result

    retrieval = RetrievalResult(papers=[paper()], new_count=1, cursor="c1")
    assert RetrievalResult.model_validate_json(retrieval.model_dump_json()) == retrieval


def test_topic_run_report_contracts() -> None:
    topic = Topic(id="ai-agents", name="AI", scope_statement="llm agents")
    assert topic.status.value == "active"
    assert Run(id="r1", topic_id="ai-agents").state is RunState.PENDING

    report = Report(
        report_id="rep-1",
        topic_id="ai-agents",
        run_id="r1",
        content_md="# weekly",
        content_sha="abc123",
        claims=[Claim(text="x", support=Support.UNSUPPORTED)],
    )
    assert report.n_claims == 0  # 由写库方补齐
    assert ReportDraft(content_md="# x").degraded is False


def test_analysis_result_and_author() -> None:
    assert AnalysisResult(findings=["a"]).by_paper == {}
    assert Author(author_id="A1", name="Ada", name_norm="ada").name_norm == "ada"


def test_severity_vocabulary_is_log_levels() -> None:
    assert {s.value for s in Severity} == {"debug", "info", "warning", "error", "critical"}

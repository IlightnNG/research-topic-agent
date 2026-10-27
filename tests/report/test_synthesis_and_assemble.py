"""3.2 / S5–S6：方向综合、报告组装、校验与 v2 接线。"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from lit_agent.models.claim import Claim
from lit_agent.models.evidence import Citation, Support
from lit_agent.report.assemble import assemble_report, build_report_v2, validate_report
from lit_agent.report.claims import ClaimSet
from lit_agent.report.clusters import Direction
from lit_agent.report.context import ReportContext
from lit_agent.report.synthesis import InsightItem, synthesize_direction


def claim(cid: str, text: str = "tool use improves success") -> Claim:
    return Claim(
        text=text,
        citations=[Citation(paper_id=cid.split("-")[0], snippet=text)],
        support=Support.SUPPORTED,
        claim_id=cid,
    )


def direction() -> Direction:
    return Direction(id="D1", name="Tool use", paper_ids=["P1", "P2"], claim_ids=["P1-C1", "P2-C1"])


class FakeGateway:
    def __init__(self, payload: dict, *, fail: bool = False) -> None:
        self.payload = payload
        self.fail = fail

    def chat_json(self, messages, **kwargs):  # type: ignore[no-untyped-def]
        if self.fail:
            raise RuntimeError("down")
        return self.payload, None


def test_synthesis_accepts_only_known_claims() -> None:
    claims = [claim("P1-C1"), claim("P2-C1", "agents use tools")]
    gateway = FakeGateway(
        {
            "definition": "Tool-using agents.",
            "common_ground": [{"text": "both improve success", "claim_ids": ["P1-C1", "P2-C1"]}],
            "differences": [{"text": "different data", "claim_ids": ["P1-C1", "P9-C1"]}],
            "open_questions": [{"text": "what next", "claim_ids": ["P1-C1"]}],
        }
    )
    insight = synthesize_direction(direction(), claims, gateway=gateway)

    assert insight.generated_by == "llm"
    assert insight.common_ground[0].claim_ids == ["P1-C1", "P2-C1"]
    assert all("P9-C1" not in item.claim_ids for item in insight.differences)


def test_synthesis_falls_back_on_failure() -> None:
    claims = [claim("P1-C1"), claim("P2-C1")]
    insight = synthesize_direction(direction(), claims, gateway=FakeGateway({}, fail=True))

    assert insight.generated_by == "template"
    assert insight.common_ground


def test_synthesis_empty_uses_deterministic() -> None:
    claims = [claim("P1-C1"), claim("P2-C1")]
    insight = synthesize_direction(direction(), claims, gateway=None)
    assert insight.generated_by == "template"
    assert len(insight.common_ground) >= 1


def test_assemble_and_validate() -> None:
    from lit_agent.report.cards import PaperCard

    cards = [
        PaperCard(paper_id="P1", title="A", claims=[{"text": "x", "quote": "x"}]),
        PaperCard(paper_id="P2", title="B", claims=[{"text": "y", "quote": "y"}]),
    ]
    claims = [claim("P1-C1"), claim("P2-C1", "agents use tools")]
    context = ReportContext(
        cards=cards,
        claim_set=ClaimSet(claims=claims),
        directions=[direction()],
    )
    from lit_agent.report.synthesis import DirectionInsight

    insight = DirectionInsight(
        direction_id="D1",
        name="Tool use",
        definition="Tool-using agents.",
        common_ground=[InsightItem(text="shared", claim_ids=["P1-C1", "P2-C1"])],
        generated_by="template",
    )
    report = assemble_report(
        run_id="r1",
        topic_id="t",
        title="Weekly",
        period="2026-W44",
        context=context,
        insights=[insight],
        language="en",
        generated_by="template",
    )

    assert report.sections
    assert "[C1]" in report.content_md
    assert validate_report(report).ok is True


def test_validation_rejects_missing_claim() -> None:
    from lit_agent.models.report import Report, ReportSection

    report = Report(
        report_id="r:1",
        topic_id="t",
        run_id="r",
        content_md="# x\nbody",
        content_sha="x",
        sections=[ReportSection(id="s", title="S", body="no cite", kind="deep_dive")],
    )
    result = validate_report(report)
    assert result.ok is False
    assert any("no claim_indexes" in error for error in result.errors)


def test_v2_builder_and_run_wiring(tmp_path: Path) -> None:
    from lit_agent.runtime.graph_runner import run_graph
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=2)
    pipeline = settings.report.model_copy(update={"v2_enabled": True})
    settings = settings.model_copy(update={"report": pipeline})
    out = run_graph(settings, "ai-agents", run_id="v2-run", focus_hint="tool use")

    assert out["state"] == "succeeded"
    conn = sqlite3.connect(settings.storage.sqlite_file)
    row = conn.execute(
        "SELECT sections_json, language, generated_by FROM reports WHERE run_id='v2-run'"
    ).fetchone()
    conn.close()

    assert row is not None
    sections = json.loads(row[0] or "[]")
    assert sections
    assert any(section["kind"] == "deep_dive" for section in sections)
    assert row[1] == "en"
    assert row[2] == "template"


def test_v2_builder_empty_papers_is_safe(tmp_path: Path) -> None:
    from tests.wiring import prepare

    settings = prepare(tmp_path, papers=0)
    report = build_report_v2(
        settings,
        run_id="empty",
        topic_id="ai-agents",
        paper_ids=[],
        title="Weekly",
    )
    assert report.degraded is True
    assert report.language == "en"
    assert report.sections

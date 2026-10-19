"""契约 ↔ 文档一致性：guide §2.3 的模型清单必须逐个存在于 `models`。"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from lit_agent import models

GUIDE = Path(__file__).resolve().parents[2] / "docs" / "implementation" / "implementation-guide.md"


def guide_model_names() -> set[str]:
    text = GUIDE.read_text(encoding="utf-8")
    section = text.split("### 2.3 Pydantic 模型清单", 1)[1].split("\n### ", 1)[0]
    names = set(re.findall(r"`([A-Z][A-Za-z]+)\{", section))
    # 阶段产物写成 "`A / B / C / D`"：单独抓取斜杠分隔的大驼峰名
    for group in re.findall(r"`([A-Za-z]+(?: / [A-Za-z]+)+)`", section):
        names.update(part.strip() for part in group.split("/") if part.strip())
    return names


def test_guide_names_all_exist() -> None:
    names = guide_model_names()
    assert names, "未从 guide §2.3 解析出任何模型名（文档格式变了？）"
    missing = sorted(name for name in names if name not in models.__all__)
    assert not missing, f"guide 声明但 models 未导出：{missing}"


def test_phase1_field_increments_exist() -> None:
    """ADR-0005 §10 / ADR-0001 的字段增量必须落在模型上。"""
    paper_fields = set(models.Paper.model_fields)
    assert {
        "merged_ids",
        "source_id",
        "venue_id",
        "is_oa",
        "language",
        "parse_status",
    } <= paper_fields

    assert "dedupe_key" in models.Event.model_fields
    assert {"content_sha", "n_claims", "degraded"} <= set(models.Report.model_fields)
    assert {"next_seq", "dup_events", "input_hash", "stage", "last_ok_stage"} <= set(
        models.Run.model_fields
    )
    assert {"claim_id", "text_sha", "report_id"} <= set(models.Claim.model_fields)


def test_verdict_shape_matches_design_doc() -> None:
    """design §7：`GuardVerdict{ok, severity, action, code, reasons[]}`。"""
    assert set(models.Verdict.model_fields) == {"ok", "severity", "action", "code", "reasons"}


@pytest.mark.parametrize("name", ["Paper", "Event", "Report", "Run", "Claim", "Verdict", "Topic"])
def test_contract_models_forbid_extra(name: str) -> None:
    model = getattr(models, name)
    assert model.model_config["extra"] == "forbid"

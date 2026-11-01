"""Phase 4.1.4: tool schema, registry, timeout/retry, packs."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from lit_agent_v2.contracts.tool import ToolSpec
from lit_agent_v2.tools.packs.claims import build_claim_tools
from lit_agent_v2.tools.packs.corpus import build_corpus_tools
from lit_agent_v2.tools.packs.report import build_report_tools
from lit_agent_v2.tools.registry import ToolRegistry


def test_schema_validation() -> None:
    registry = ToolRegistry(
        [ToolSpec("echo", "echo", {"type": "object", "properties": {"q": {"type": "string"}}, "required": ["q"]}, handler=lambda a: a)]
    )
    assert registry.call("echo", {"q": "x"}).ok
    missing = registry.call("echo", {})
    assert missing.error_code == "E_TOOL_SCHEMA"
    wrong = registry.call("echo", {"q": 1})
    assert wrong.error_code == "E_TOOL_SCHEMA"


def test_registry_duplicate_and_subset() -> None:
    spec = ToolSpec("echo", "echo", handler=lambda a: a)
    registry = ToolRegistry([spec])
    with pytest.raises(ValueError):
        registry.register(spec)
    sub = registry.subset(["echo"])
    assert sub.names() == ["echo"]
    assert sub.call("echo", {}).ok


def test_timeout_and_retry() -> None:
    calls = 0

    def slow(_args):
        nonlocal calls
        calls += 1
        time.sleep(0.05)
        return {}

    registry = ToolRegistry(
        [ToolSpec("slow", "slow", timeout_s=0.01, max_retries=1, handler=slow)]
    )
    result = registry.call("slow", {})
    assert result.error_code == "E_TOOL_TIMEOUT"
    assert calls == 2


def test_corpus_tools(tmp_path: Path) -> None:
    registry = ToolRegistry(build_corpus_tools())
    papers = [
        {"paper_id": "P1", "title": "A", "abstract": "x"},
        {"paper_id": "P1", "title": "A duplicate", "abstract": "y"},
        {"paper_id": "P2", "title": "B", "abstract": "z"},
    ]
    stored = registry.call("corpus.store", {"root": str(tmp_path / "corpus"), "papers": papers})
    assert stored.ok
    deduped = registry.call("corpus.dedupe", {"papers": papers})
    assert deduped.output["kept"] == 2
    stats = registry.call("corpus.stats", {"root": str(tmp_path / "corpus")})
    assert stats.output["papers"] == 3
    read = registry.call("corpus.papers", {"root": str(tmp_path / "corpus"), "limit": 2})
    assert read.output["count"] == 2


def test_claim_and_quote_tools() -> None:
    registry = ToolRegistry(build_claim_tools())
    text = "We find that tool use improves agent success on benchmark tasks."
    claims = registry.call("claims.extract", {"paper_id": "P1", "text": text})
    assert claims.ok
    assert claims.output["count"] == 1
    quote = registry.call(
        "quote.check",
        {"quote": "tool use improves agent success", "text": text},
    )
    assert quote.output["ok"] is True


def test_report_tools() -> None:
    registry = ToolRegistry(build_report_tools())
    papers = [{"paper_id": f"P{index}"} for index in range(12)]
    plan = registry.call("report.plan", {"papers": papers, "chunk_size": 5})
    assert plan.ok
    kinds = [section["kind"] for section in plan.output["sections"]]
    assert kinds == [
        "overview",
        "paper_analysis",
        "paper_analysis",
        "paper_analysis",
        "synthesis",
        "paper_index",
    ]

    section = {"body": "Finding [C1]", "section_id": "x"}
    checked = registry.call(
        "report.check_section",
        {"section": section, "claims": [{"claim_id": "P1-C1"}]},
    )
    assert checked.output["ok"] is True

    assembled = registry.call(
        "report.assemble",
        {"title": "T", "sections": [section]},
    )
    assert assembled.output["word_count"] == 2


class SectionLLM:
    def chat_json(self, messages, **kwargs):  # noqa: ANN001
        return {"body": "The corpus studies tool use [C1]. It also studies citations [C2]."}, None


def test_write_section_and_persist(tmp_path: Path) -> None:
    registry = ToolRegistry(build_report_tools(SectionLLM()))
    section = {"section_id": "s1", "kind": "overview", "title": "Overview"}
    claims = [
        {"claim_id": "C1", "paper_id": "P1", "quote": "q1"},
        {"claim_id": "C2", "paper_id": "P2", "quote": "q2"},
    ]
    written = registry.call("report.write_section", {"section": section, "claims": claims})
    assert written.output["ok"] is True
    assert written.output["section"]["body"].startswith("The corpus")

    persisted = registry.call(
        "report.persist",
        {
            "root": str(tmp_path / "out"),
            "title": "T",
            "content_md": "Body [C1].",
            "claims": claims,
        },
    )
    assert persisted.ok
    assert Path(persisted.output["markdown_path"]).exists()
    assert Path(persisted.output["path"]).exists()

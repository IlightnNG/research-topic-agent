"""Code checks for Node outputs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.node import NodeContext, NodeResult, NodeSpec
from lit_agent_v2.contracts.verdict import CodeCheck

__all__ = ["CodeVerifier"]

_CITATION = re.compile(r"\[C(\d+)\]")
_APPENDIX = {"paper_index", "claim_ledger"}


class CodeVerifier:
    def verify(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> list[CodeCheck]:
        checks: list[CodeCheck] = []
        for check_id in node.verifier.code:
            fn = getattr(self, f"_check_{check_id}", None)
            if fn is None:
                checks.append(CodeCheck(check_id, False, f"unknown code check: {check_id}"))
                continue
            try:
                checks.append(fn(node, context, result))
            except Exception as exc:  # noqa: BLE001
                checks.append(CodeCheck(check_id, False, f"{type(exc).__name__}: {exc}"))
        return checks

    def _check_schema(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        if not isinstance(result.output, dict):
            return CodeCheck("schema", False, "output must be an object")
        schema = context.output_schema
        if isinstance(schema, dict) and schema:
            problems = _validate(result.output, schema)
            if problems:
                return CodeCheck("schema", False, "; ".join(problems))
        return CodeCheck("schema", True)

    def _check_papers(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        papers = result.output.get("papers")
        if not isinstance(papers, list) or not papers:
            return CodeCheck("papers", False, "papers must be a non-empty list")
        ids = [str(paper.get("paper_id") or "") for paper in papers if isinstance(paper, dict)]
        if len(ids) != len(papers) or any(not paper_id for paper_id in ids):
            return CodeCheck("papers", False, "every paper needs paper_id")
        if len(ids) != len(set(ids)):
            return CodeCheck("papers", False, "duplicate paper_id")
        return CodeCheck("papers", True)

    def _check_dedupe(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        papers = result.output.get("papers")
        if not isinstance(papers, list):
            return CodeCheck("dedupe", False, "papers missing")
        titles = [
            str(paper.get("title") or "").strip().lower()
            for paper in papers
            if isinstance(paper, dict)
        ]
        if len(titles) != len(set(titles)):
            return CodeCheck("dedupe", False, "duplicate title")
        return CodeCheck("dedupe", True)

    def _check_claim(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        claims = result.output.get("claims")
        if not isinstance(claims, list) or not claims:
            return CodeCheck("claim", False, "claims must be non-empty")
        ids = [str(claim.get("claim_id") or "") for claim in claims if isinstance(claim, dict)]
        if len(ids) != len(claims) or any(not claim_id for claim_id in ids):
            return CodeCheck("claim", False, "every claim needs claim_id")
        if len(ids) != len(set(ids)):
            return CodeCheck("claim", False, "duplicate claim_id")
        return CodeCheck("claim", True)

    def _check_quote(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        claims = result.output.get("claims")
        if not isinstance(claims, list) or not claims:
            return CodeCheck("quote", False, "claims missing")
        source = str(result.output.get("text") or "")
        for claim in claims:
            quote = str(claim.get("quote") or "") if isinstance(claim, dict) else ""
            if not quote.strip():
                return CodeCheck("quote", False, "empty quote")
            if source and " ".join(quote.split()) not in " ".join(source.split()):
                return CodeCheck("quote", False, "quote not found in source text")
        return CodeCheck("quote", True)

    def _check_citation(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        body = _report_body(result.output)
        if not body.strip():
            return CodeCheck("citation", False, "empty report body")
        if not _CITATION.search(body):
            return CodeCheck("citation", False, "no [C#] citation")
        claims = result.output.get("claims")
        if isinstance(claims, list) and claims:
            cited = {int(raw) for raw in _CITATION.findall(body)}
            if max(cited, default=0) > len(claims):
                return CodeCheck("citation", False, "citation points past claim list")
        return CodeCheck("citation", True)

    def _check_count(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        pairs = (("claims", "claim_count"), ("papers", "paper_count"), ("sections", "section_count"))
        for list_key, count_key in pairs:
            if (
                list_key in result.output
                and count_key in result.output
                and len(result.output[list_key]) != result.output[count_key]
            ):
                return CodeCheck("count", False, f"{list_key} != {count_key}")
        return CodeCheck("count", True)

    def _check_word_limit(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        body = _report_body(result.output)
        words = len(body.split())
        if words > 8000:
            return CodeCheck("word_limit", False, f"{words} words > 8000")
        return CodeCheck("word_limit", True)

    def _check_file_exists(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        raw = result.output.get("path") or result.output.get("file")
        if not raw:
            return CodeCheck("file_exists", False, "missing path/file")
        if not Path(str(raw)).exists():
            return CodeCheck("file_exists", False, f"missing file: {raw}")
        return CodeCheck("file_exists", True)

    def _check_directions(
        self, node: NodeSpec, context: NodeContext, result: NodeResult
    ) -> CodeCheck:
        directions = result.output.get("directions")
        if not isinstance(directions, list) or not directions:
            return CodeCheck("directions", False, "directions missing")
        if len(directions) > 8:
            return CodeCheck("directions", False, "more than 8 directions")
        return CodeCheck("directions", True)


def _report_body(output: dict[str, Any]) -> str:
    if isinstance(output.get("content_md"), str):
        return output["content_md"]
    sections = output.get("sections")
    if isinstance(sections, list):
        return "\n\n".join(
            str(section.get("body") or "")
            for section in sections
            if isinstance(section, dict) and section.get("kind") not in _APPENDIX
        )
    return ""


def _validate(value: Any, schema: dict[str, Any]) -> list[str]:
    expected = schema.get("type")
    if expected == "object":
        if not isinstance(value, dict):
            return ["output must be object"]
        problems = []
        for key in schema.get("required") or []:
            if key not in value:
                problems.append(f"missing field: {key}")
        return problems
    if expected == "array" and not isinstance(value, list):
        return ["output must be array"]
    return []


def _json_preview(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)[:200]

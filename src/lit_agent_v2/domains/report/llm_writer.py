"""M4-P02: per-direction LLM writer with deterministic fallback."""

from __future__ import annotations

import json
import re
from typing import Any, Protocol

from lit_agent_v2.contracts.report import (
    EvidenceArtifact,
    MapArtifact,
    ReportDraft,
    Section,
)
from lit_agent_v2.domains.report.audit import audit_report
from lit_agent_v2.domains.report.plan import EvidencePack, ReportPlan, build_plan, pack_for
from lit_agent_v2.domains.report.policy import policy_for
from lit_agent_v2.domains.report.write import WriteService

__all__ = ["ChatClient", "LLMReportWriter"]

_CITATION = re.compile(r"\[C(\d+)\]")
_HEADING = re.compile(r"^#{1,4}\s+")


class ChatClient(Protocol):
    def chat_json(self, messages: list[dict[str, str]], **kwargs: Any) -> tuple[dict, Any]: ...


class LLMReportWriter:
    def __init__(self, llm: ChatClient, *, max_attempts: int = 2) -> None:
        self.llm = llm
        self.max_attempts = max_attempts
        self.fallback = WriteService()
        self.errors: list[str] = []
        self.fallback_sections: list[str] = []

    def build(
        self,
        *,
        run_id: str,
        topic_id: str,
        title: str,
        evidence: EvidenceArtifact,
        mapping: MapArtifact,
        on_section=None,
    ) -> ReportDraft:
        policy = policy_for(len(evidence.papers), evidence.claims)
        plan = build_plan(title=title, evidence=evidence, mapping=mapping, policy=policy)
        fallback = self.fallback.build(
            run_id=run_id, topic_id=topic_id, title=title, evidence=evidence, mapping=mapping
        )
        fallback_by_id = {section.section_id: section for section in fallback.sections}
        index_of = {str(claim["claim_id"]): index for index, claim in enumerate(fallback.claims)}
        sections: list[Section] = []
        accepted = True
        self.errors = []
        self.fallback_sections = []
        self.decisions: list[tuple[str, bool]] = []

        for planned in plan.sections:
            if planned.kind == "deep_dive":
                section, ok = self._direction(
                    planned, plan, evidence, mapping, index_of, fallback_by_id
                )
            elif planned.kind == "overview":
                section, ok = self._overview(planned, sections, evidence, mapping, fallback_by_id)
            elif planned.kind == "comparison":
                section, ok = self._comparison(
                    planned, sections, fallback_by_id, index_of
                )
            else:
                section, ok = fallback_by_id[planned.section_id], True
            self.decisions.append((planned.section_id, ok))
            accepted = accepted and (ok or planned.kind in {"overview", "comparison"})
            sections.append(section)
            if on_section is not None:
                on_section(section)

        body = "\n\n".join(section.body for section in sections)
        draft = ReportDraft(
            title=title,
            content_md=body,
            content_sha="",
            sections=sections,
            word_count=0,
            claims=fallback.claims,
            state="degraded",
        )
        import hashlib

        draft.content_sha = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        audit = audit_report(draft)
        max_share = max((len(item.paper_ids) for item in mapping.directions), default=0) / max(
            1, mapping.papers
        )
        draft.word_count = audit.narrative_words
        draft.state = (
            "complete"
            if accepted
            and mapping.count_quality == "complete"
            and evidence.fulltext_ratio >= 0.3
            and policy.min_words <= audit.narrative_words <= policy.max_words
            and policy.min_directions <= len(mapping.directions) <= policy.max_directions
            and mapping.min_size >= policy.min_direction_size
            and max_share <= policy.max_direction_share
            and audit.citation_coverage >= 1.0
            and audit.uncited_facts == 0
            and audit.duplicate_claim_rate <= 0.1
            else "degraded"
        )
        return draft

    def _direction(
        self,
        planned,
        plan: ReportPlan,
        evidence: EvidenceArtifact,
        mapping: MapArtifact,
        index_of: dict[str, int],
        fallback_by_id: dict[str, Section],
    ) -> tuple[Section, bool]:
        pack = pack_for(plan, planned.section_id, evidence, mapping)
        if pack is None:
            self.errors.append(f"{planned.section_id}:fallback")
            return fallback_by_id[planned.section_id], False
        prompt = self._direction_prompt(pack)
        for _attempt in range(self.max_attempts):
            try:
                payload, _usage = self.llm.chat_json(
                    prompt,
                    max_tokens=8000,
                    temperature=0.2,
                )
            except Exception as exc:  # noqa: BLE001
                self.errors.append(f"{planned.section_id}:{type(exc).__name__}:{exc}:{getattr(exc, 'details', {})}")
                continue
            structured = payload.get("common_ground") is not None
            if structured:
                built = self._structured_body(payload, pack)
                if built is None:
                    self.errors.append(f"{planned.section_id}:schema:{str(payload)[:300]}")
                    continue
                body, cited = built
            else:
                body = str(payload.get("body") or "").strip()
                cited = set()
            if not body:
                self.errors.append(f"{planned.section_id}:empty")
                continue
            known = {item["ref"]: str(item["claim_id"]) for item in pack.claims}
            refs = _CITATION.findall(body)
            unknown = [ref for ref in refs if f"C{ref}" not in known]
            if unknown:
                self.errors.append(f"{planned.section_id}:unknown_ref")
                continue
            if not cited:
                cited = {known[f"C{ref}"] for ref in refs if f"C{ref}" in known}
            if len(cited) / max(1, len(pack.claims)) < 0.5:
                self.errors.append(f"{planned.section_id}:coverage")
                continue
            uncited = [
                line
                for line in body.splitlines()
                if line.strip().startswith("- ") and not _CITATION.search(line)
            ]
            if uncited:
                self.errors.append(f"{planned.section_id}:uncited")
                continue
            if len(refs) != len(set(refs)):
                self.errors.append(f"{planned.section_id}:duplicate")
                continue
            body = self._append_missing(body, pack, cited, known)
            indexes = sorted(
                index_of[str(item["claim_id"])]
                for item in pack.claims
                if str(item["claim_id"]) in index_of
            )
            return (
                Section(
                    planned.section_id,
                    "deep_dive",
                    planned.title,
                    f"## {planned.title}\n\n{body}",
                    indexes,
                ),
                True,
            )
        self.errors.append(f"{planned.section_id}:fallback")
        return fallback_by_id[planned.section_id], False

    def _structured_body(
        self, payload: dict, pack: EvidencePack
    ) -> tuple[str, set[str]] | None:
        known = {item["ref"]: str(item["claim_id"]) for item in pack.claims}
        headings = {
            "common_ground": "Common ground",
            "differences": "Differences",
            "open_questions": "Open questions",
        }
        lines: list[str] = []
        cited: set[str] = set()
        seen: set[str] = set()
        for key, heading in headings.items():
            entries = payload.get(key) or []
            if not isinstance(entries, list):
                return None
            lines.append(f"### {heading}")
            for entry in entries:
                if not isinstance(entry, dict):
                    return None
                text = str(entry.get("text") or "").strip()
                refs = entry.get("refs") or _CITATION.findall(text)
                text = _CITATION.sub("", text).strip()
                refs = [str(ref).lstrip("C") for ref in refs if str(ref).strip()]
                if not text or not refs:
                    continue
                valid = []
                for ref in refs:
                    if f"C{ref}" in known and f"C{ref}" not in seen:
                        valid.append(ref)
                if not valid:
                    continue
                seen.update(f"C{ref}" for ref in valid)
                cited.update(known[f"C{ref}"] for ref in valid)
                suffix = " ".join(f"[C{ref}]" for ref in valid)
                lines.append(f"- {text} {suffix}")
        if not cited:
            return None
        return "\n".join(lines), cited

    def _append_missing(
        self, body: str, pack: EvidencePack, cited: set[str], known: dict[str, str]
    ) -> str:
        missing = [item for item in pack.claims if str(item["claim_id"]) not in cited]
        if not missing:
            return body
        lines = [body, "", "### Evidence notes"]
        for item in missing:
            lines.append(f"- `{item['paper_id']}`: {item['text']} [{item['ref']}]")
        return "\n".join(lines)

    def _overview(self, planned, sections, evidence, mapping, fallback_by_id) -> tuple[Section, bool]:
        claims = sum(len(paper.get("claims", [])) for paper in evidence.papers)
        summary = "\n".join(
            f"- {section.title}: {section.body[:300]}" for section in sections if section.kind == "deep_dive"
        )
        prompt = [
            {
                "role": "system",
                "content": (
                    "Write a 100-180 word report overview. Use only the supplied counts and "
                    "section summaries. No new facts. No claim citations required. Return JSON "
                    '{"body":str} only.'
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "papers": len(evidence.papers),
                        "claims": claims,
                        "directions": len(mapping.directions),
                        "fulltext": evidence.fulltext,
                        "sections": summary,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        try:
            payload, _ = self.llm.chat_json(prompt, max_tokens=800)
            body = str(payload.get("body") or "").strip()
            if body:
                return Section("overview", "overview", "At a Glance", f"# {planned.title}\n\n{body}"), True
        except Exception as exc:  # noqa: BLE001
            self.errors.append(f"overview:{type(exc).__name__}:{exc}")
        else:
            self.errors.append("overview:empty")
        self.fallback_sections.append("overview")
        return fallback_by_id["overview"], False

    def _comparison(self, planned, sections, fallback_by_id, index_of) -> tuple[Section, bool]:
        fallback = fallback_by_id["comparison"]
        rows = [line for line in fallback.body.splitlines() if line.startswith("|")]
        prompt = [
            {
                "role": "system",
                "content": (
                    "Write a 120-200 word comparison of the provided directions. Use only "
                    "the table. Do not invent numbers. Return JSON {\"body\":str} only."
                ),
            },
            {"role": "user", "content": "\n".join(rows)},
        ]
        try:
            payload, _ = self.llm.chat_json(prompt, max_tokens=1000)
            body = str(payload.get("body") or "").strip()
            if body:
                return (
                    Section(
                        "comparison",
                        "comparison",
                        "Comparison Matrix",
                        f"## Comparison Matrix\n\n{body}\n\n" + "\n".join(rows),
                        fallback.claim_indexes,
                    ),
                    True,
                )
        except Exception as exc:  # noqa: BLE001
            self.errors.append(f"comparison:{type(exc).__name__}:{exc}")
        else:
            self.errors.append("comparison:empty")
        self.fallback_sections.append("comparison")
        return fallback, False

    def _direction_prompt(self, pack: EvidencePack) -> list[dict[str, str]]:
        claims = [
            {"ref": item["ref"], "paper": item["paper_id"], "type": item["claim_type"], "text": item["text"]}
            for item in pack.claims
        ]
        return [
            {
                "role": "system",
                "content": (
                    "Write ONE research report section. Use only the supplied claims. "
                    "Every factual sentence must end with [C#] from the supplied refs. "
                    "Do not introduce new papers, numbers, or claims. "
                    "Do not repeat the same claim in more than one bullet. "
                    f"Target {pack.target_words} words. Return JSON only: "
                    '{"common_ground":[{"text":str,"refs":["C1"]}],'
                    '"differences":[{"text":str,"refs":["C2"]}],'
                    '"open_questions":[{"text":str,"refs":["C3"]}]}. '
                    "One claim per bullet; refs must come from supplied claims. "
                    "Do not return markdown." 
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "direction": pack.name,
                        "papers": pack.papers,
                        "claims": claims,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

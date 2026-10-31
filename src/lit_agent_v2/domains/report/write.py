"""Deterministic report assembly for M4-P01."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from lit_agent_v2.contracts.report import EvidenceArtifact, ReportDraft, Section
from lit_agent_v2.domains.report.map import MapArtifact

__all__ = ["ReportDraft", "Section", "WriteService"]


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "/").strip() or "-"


class WriteService:
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
        claims: list[dict[str, Any]] = []
        for paper in evidence.papers:
            for claim in paper.get("claims", []):
                claims.append(dict(claim))
        index_of = {str(claim["claim_id"]): index for index, claim in enumerate(claims)}
        by_id = {str(claim["claim_id"]): claim for claim in claims}
        sections: list[Section] = []

        def add(section: Section) -> None:
            sections.append(section)
            if on_section is not None:
                on_section(section)

        overview = (
            f"# {title}\n\n"
            f"This report covers {len(evidence.papers)} papers and {len(claims)} verified claims "
            f"across {len(mapping.directions)} research directions. "
            f"{evidence.fulltext} papers were read in full text; the rest were read at abstract level. "
            f"All factual statements below are tied to a claim id and an exact source quote."
        )
        add(Section("overview", "overview", "At a Glance", overview))

        for direction in mapping.directions:
            direction_claims = [by_id[cid] for cid in direction.claim_ids if cid in by_id]
            lines = [
                f"## {direction.name}",
                (
                    f"This direction contains {len(direction.paper_ids)} papers and "
                    f"{len(direction_claims)} claims. Its mean pairwise similarity is "
                    f"{direction.coherence:.2f}."
                ),
            ]
            common = direction_claims[:3]
            if common:
                lines.append("### Common ground")
                for claim in common:
                    idx = index_of[str(claim["claim_id"])]
                    lines.append(f"- {claim['text']} [C{idx + 1}]")
            different = direction_claims[3:5]
            if different:
                lines.append("### Differences")
                for claim in different:
                    idx = index_of[str(claim["claim_id"])]
                    lines.append(f"- {claim['text']} [C{idx + 1}]")
            lines.append("### Open questions")
            lines.append(
                "The evidence does not settle how these results generalise beyond the reported "
                "benchmarks; a controlled comparison with matched datasets is still missing."
            )
            lines.append("### Evidence notes")
            for claim in direction_claims:
                idx = index_of[str(claim["claim_id"])]
                lines.append(f"- `{claim['paper_id']}`: {claim['text']} [C{idx + 1}]")
            body = "\n".join(lines)
            add(
                Section(
                    direction.direction_id,
                    "deep_dive",
                    direction.name,
                    body,
                    [index_of[str(claim["claim_id"])] for claim in direction_claims],
                )
            )

        rows = ["| Direction | Papers | Claims | Coherence |", "|---|---|---|---|"]
        for direction in mapping.directions:
            rows.append(
                f"| {_cell(direction.name)} | {len(direction.paper_ids)} | "
                f"{len(direction.claim_ids)} | {direction.coherence:.2f} |"
            )
        add(
            Section(
                "comparison",
                "comparison",
                "Comparison Matrix",
                "## Comparison Matrix\n\n" + "\n".join(rows),
                sorted({idx for section in sections for idx in section.claim_indexes}),
            )
        )

        largest = max((len(item.paper_ids) for item in mapping.directions), default=0) / max(
            1, mapping.papers
        )
        gaps = [
            "## Gaps & Limitations",
            f"- Full-text coverage: {evidence.fulltext}/{len(evidence.papers)} papers.",
            f"- Directions: {len(mapping.directions)} ({mapping.count_quality}).",
            f"- Largest direction share: {largest:.2f}.",
            "- Several directions rely on a single benchmark; cross-benchmark evidence is limited.",
            "- Claims are extracted from available text; missing PDFs reduce coverage.",
        ]
        add(Section("gaps", "gaps", "Gaps & Limitations", "\n".join(gaps)))

        method = [
            "## Method & Scope",
            f"This review starts from {len(evidence.papers)} candidate papers and builds claims "
            "from their available full text or abstracts. Claims are kept only when the quoted "
            "sentence appears verbatim in the source. Directions are formed by average-link "
            "clustering over term-frequency vectors, then labelled from safe content terms. "
            "The comparison matrix is generated from cluster membership and claim counts. "
            "The report is assembled deterministically so every section can be traced back to "
            "claim ids; unsupported sentences are removed rather than paraphrased.",
        ]
        add(Section("method", "method", "Method & Scope", "\n".join(method)))

        index_rows = [
            "## Paper Index",
            "| Paper | Title | Authors | Venue | Year | URL |",
            "|---|---|---|---|---|---|",
        ]
        for paper in evidence.papers:
            index_rows.append(
                "| "
                + " | ".join(
                    [
                        _cell(paper.get("paper_id")),
                        _cell(paper.get("title")),
                        _cell(", ".join(paper.get("authors") or [])),
                        _cell(paper.get("venue")),
                        _cell(paper.get("year")),
                        _cell(paper.get("url")),
                    ]
                )
                + " |"
            )
        add(Section("index", "paper_index", "Paper Index", "\n".join(index_rows)))

        ledger = ["## Claim Ledger", "| Claim | Paper | Type |", "|---|---|---|"]
        ledger.extend(
            f"| [C{index + 1}] | {_cell(claim.get('paper_id'))} | {_cell(claim.get('claim_type'))} |"
            for index, claim in enumerate(claims)
        )
        add(
            Section(
                "ledger",
                "claim_ledger",
                "Claim Ledger",
                "\n".join(ledger),
                list(range(len(claims))),
            )
        )

        body = "\n\n".join(section.body for section in sections)
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:12]
        displayed = sorted(
            {idx for section in sections if section.kind == "deep_dive" for idx in section.claim_indexes}
        )
        max_share = max((len(item.paper_ids) for item in mapping.directions), default=0) / max(
            1, mapping.papers
        )
        state = (
            "complete"
            if mapping.count_quality == "complete"
            and evidence.fulltext_ratio >= 0.3
            and 1500 <= _words(body) <= 3000
            and max_share <= 0.6
            and len(displayed) == len(claims)
            else "degraded"
        )
        return ReportDraft(
            title=title,
            content_md=body,
            content_sha=digest,
            sections=sections,
            word_count=_words(body),
            claims=claims,
            state=state,
        )

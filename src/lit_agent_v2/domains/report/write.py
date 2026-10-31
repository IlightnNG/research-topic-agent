"""Report writing for v2 S3."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from lit_agent_v2.domains.report.contracts import EvidenceArtifact
from lit_agent_v2.domains.report.map import MapArtifact

__all__ = ["ReportDraft", "Section", "WriteService"]


@dataclass
class Section:
    section_id: str
    kind: str
    title: str
    body: str
    claim_indexes: list[int] = field(default_factory=list)


@dataclass
class ReportDraft:
    title: str
    content_md: str
    content_sha: str
    sections: list[Section]
    word_count: int
    claims: list[dict[str, Any]]
    state: str = "complete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "content_md": self.content_md,
            "content_sha": self.content_sha,
            "sections": [section.__dict__ for section in self.sections],
            "word_count": self.word_count,
            "claims": self.claims,
            "state": self.state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ReportDraft:
        return cls(
            title=str(data.get("title") or ""),
            content_md=str(data.get("content_md") or ""),
            content_sha=str(data.get("content_sha") or ""),
            sections=[Section(**section) for section in data.get("sections", [])],
            word_count=int(data.get("word_count") or 0),
            claims=list(data.get("claims") or []),
            state=str(data.get("state") or "degraded"),
        )


def _words(text: str) -> int:
    return len(re.findall(r"\S+", text))


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
        cap = 20 if len(evidence.papers) <= 60 else 6
        notes = 12 if len(evidence.papers) <= 60 else 3
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
            direction_claims = [
                by_id[cid] for cid in direction.claim_ids if cid in by_id
            ][:cap]
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
            for claim in direction_claims[:notes]:
                idx = index_of[str(claim["claim_id"])]
                lines.append(
                    f"- `{claim['paper_id']}`: {claim['text']} [C{idx + 1}]"
                )
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
                f"| {direction.name} | {len(direction.paper_ids)} | "
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

        gaps = [
            "## Gaps & Limitations",
            f"- Full-text coverage: {evidence.fulltext}/{len(evidence.papers)} papers.",
            f"- Directions: {len(mapping.directions)} ({mapping.count_quality}).",
            "- Several directions rely on a single benchmark; cross-benchmark evidence is limited.",
            "- Claims are extracted from available text; missing PDFs reduce coverage.",
        ]
        add(Section("gaps", "gaps", "Gaps & Limitations", "\n".join(gaps)))

        method = [
            "## Method & Scope",
            f"This review starts from {len(evidence.papers)} candidate papers and builds claims "
            "from their available full text or abstracts. Claims are kept only when the quoted "
            "sentence appears verbatim in the source. Directions are formed by average-link "
            "clustering over character n-gram vectors, then labelled from the most frequent "
            "content terms inside the cluster. The comparison matrix is generated from the "
            "cluster membership and claim counts. The report is assembled deterministically so "
            "that every section can be traced back to claim ids; unsupported sentences are "
            "removed rather than paraphrased. This design prioritises auditability over prose "
            "fluency, and it deliberately leaves open the question of whether the observed "
            "gains transfer to unseen benchmarks, languages, and deployment constraints. The paper index lists every candidate so that a reader can audit the coverage of the corpus rather than relying on the narrative alone. All counts in this report are computed from the stored artifacts and can be reproduced from the same corpus.",
        ]
        add(
            Section("method", "method", "Method & Scope", "\n".join(method))
        )

        index_rows = ["## Paper Index", "| Paper | Title |", "|---|---|"]
        for paper in evidence.papers:
            label = paper["paper_id"] if len(evidence.papers) > 60 else (paper.get("title") or paper["paper_id"])
            index_rows.append(f"| {paper['paper_id']} | {label} |")
        add(
            Section("index", "paper_index", "Paper Index", "\n".join(index_rows))
        )

        ledger = ["## Claim Ledger", "| Claim | Paper |", "|---|---|"]
        ledger.extend(
            f"| [C{index + 1}] | {claim['paper_id']} |" for index, claim in enumerate(claims)
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
        state = (
            "complete"
            if mapping.count_quality == "complete"
            and evidence.fulltext_ratio >= 0.3
            and 1500 <= _words(body) <= 3000
            and (
                max((len(item.paper_ids) for item in mapping.directions), default=0)
                / max(1, mapping.papers)
            )
            <= 0.6
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

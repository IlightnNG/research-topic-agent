"""Feature and report requirement contracts."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["FeatureProfile", "ReportRequirements"]


@dataclass(frozen=True)
class FeatureProfile:
    classification: bool = False
    direction_sections: bool = False
    per_paper_sections: bool = True
    synthesis: bool = True
    scorecard: bool = False
    gold_eval: bool = False
    require_fulltext: bool = False

    def enabled_sections(self) -> tuple[str, ...]:
        sections = ["overview"]
        if self.per_paper_sections:
            sections.append("paper_analysis")
        if self.synthesis:
            sections.append("synthesis")
        if self.direction_sections:
            sections.append("direction")
        sections.append("paper_index")
        return tuple(sections)


@dataclass(frozen=True)
class ReportRequirements:
    min_words: int = 800
    max_words: int = 8000
    required_sections: tuple[str, ...] = ("overview", "paper_index")
    optional_sections: tuple[str, ...] = (
        "paper_analysis",
        "synthesis",
        "direction",
        "comparison",
        "gaps",
    )
    citation_required: bool = True

    def validate_plan(self, kinds: tuple[str, ...]) -> list[str]:
        problems: list[str] = []
        for kind in self.required_sections:
            if kind not in kinds:
                problems.append(f"missing required section: {kind}")
        allowed = set(self.required_sections) | set(self.optional_sections)
        for kind in kinds:
            if kind not in allowed:
                problems.append(f"unknown section kind: {kind}")
        if not self.min_words <= self.max_words:
            problems.append("min_words > max_words")
        return problems

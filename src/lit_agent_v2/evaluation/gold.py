"""M5-P02: 100-paper gold dataset schema, validation and freeze."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["GoldCase", "GoldClaim", "GoldDataset", "GoldPaper", "load_gold"]


@dataclass
class GoldClaim:
    claim_id: str
    paper_id: str
    text: str
    quote: str
    claim_type: str = "finding"
    importance: int = 3


@dataclass
class GoldPaper:
    paper_id: str
    title: str
    authors: list[str] = field(default_factory=list)
    venue: str = ""
    year: int | None = None
    relevance: int = 3
    source_text: str = ""
    claims: list[GoldClaim] = field(default_factory=list)


@dataclass
class GoldCase:
    case_id: str
    topic_id: str
    corpus_root: str
    limit: int = 100
    focus_hint: str | None = None
    gold_directions: list[list[str]] = field(default_factory=list)
    papers: list[GoldPaper] = field(default_factory=list)


@dataclass
class GoldDataset:
    name: str
    version: str
    cases: list[GoldCase]
    sha: str = ""

    @classmethod
    def load(cls, path: str | Path) -> GoldDataset:
        root = Path(path)
        raw = root.read_bytes()
        data = json.loads(raw)
        case_items = list(data.get("cases") or [])
        cases_dir = root.parent / "cases"
        if cases_dir.exists():
            for case_path in sorted(cases_dir.glob("*.json")):
                case_items.append(json.loads(case_path.read_text(encoding="utf-8")))
        cases = [_case_from_dict(item) for item in case_items]
        dataset = cls(
            name=str(data.get("name") or "gold"),
            version=str(data.get("version") or "1.0"),
            cases=cases,
        )
        digest = hashlib.sha256(raw)
        if cases_dir.exists():
            for case_path in sorted(cases_dir.glob("*.json")):
                digest.update(case_path.name.encode())
                digest.update(case_path.read_bytes())
        dataset.sha = digest.hexdigest()[:16]
        dataset.validate()
        return dataset

    def validate(self, *, min_cases: int = 1, papers_per_case: int | None = None) -> None:
        if len(self.cases) < min_cases:
            raise ValueError(f"gold dataset needs >= {min_cases} cases")
        case_ids: set[str] = set()
        for case in self.cases:
            if not case.case_id or case.case_id in case_ids:
                raise ValueError(f"duplicate/empty case_id: {case.case_id}")
            case_ids.add(case.case_id)
            if papers_per_case is not None and len(case.papers) != papers_per_case:
                raise ValueError(
                    f"{case.case_id}: expected {papers_per_case} papers, got {len(case.papers)}"
                )
            paper_ids = {paper.paper_id for paper in case.papers}
            if len(paper_ids) != len(case.papers):
                raise ValueError(f"{case.case_id}: duplicate paper_id")
            claim_ids: set[str] = set()
            for paper in case.papers:
                if not paper.paper_id:
                    raise ValueError(f"{case.case_id}: empty paper_id")
                if not 1 <= paper.relevance <= 5:
                    raise ValueError(f"{paper.paper_id}: relevance out of range")
                if not paper.claims:
                    raise ValueError(f"{paper.paper_id}: no gold claims")
                for claim in paper.claims:
                    if claim.claim_id in claim_ids:
                        raise ValueError(f"duplicate claim_id: {claim.claim_id}")
                    claim_ids.add(claim.claim_id)
                    if claim.paper_id != paper.paper_id:
                        raise ValueError(f"{claim.claim_id}: paper mismatch")
                    if not 1 <= claim.importance <= 5:
                        raise ValueError(f"{claim.claim_id}: importance out of range")
                    source = paper.source_text
                    if source and claim.quote not in source:
                        raise ValueError(f"{claim.claim_id}: quote not verbatim")
            covered: set[str] = set()
            for direction in case.gold_directions:
                if not direction:
                    raise ValueError(f"{case.case_id}: empty gold direction")
                missing = set(direction) - paper_ids
                if missing:
                    raise ValueError(f"{case.case_id}: direction references unknown papers")
                covered.update(direction)
            if case.papers and len(covered) / len(case.papers) < 0.8:
                raise ValueError(f"{case.case_id}: direction coverage < 0.8")

    def assert_frozen(self, expected_sha: str) -> None:
        if self.sha != expected_sha:
            raise RuntimeError(f"gold dataset changed: {self.sha} != {expected_sha}")


def _case_from_dict(item: dict) -> GoldCase:
    papers = []
    for paper in item.get("papers") or []:
        claims = [
            GoldClaim(
                claim_id=str(claim["claim_id"]),
                paper_id=str(claim.get("paper_id") or paper["paper_id"]),
                text=str(claim.get("text") or ""),
                quote=str(claim.get("quote") or ""),
                claim_type=str(claim.get("claim_type") or "finding"),
                importance=int(claim.get("importance") or 3),
            )
            for claim in paper.get("claims") or []
        ]
        papers.append(
            GoldPaper(
                paper_id=str(paper["paper_id"]),
                title=str(paper.get("title") or ""),
                authors=[str(name) for name in paper.get("authors") or []],
                venue=str(paper.get("venue") or ""),
                year=paper.get("year"),
                relevance=int(paper.get("relevance") or 3),
                source_text=str(paper.get("source_text") or ""),
                claims=claims,
            )
        )
    return GoldCase(
        case_id=str(item["case_id"]),
        topic_id=str(item["topic_id"]),
        corpus_root=str(item["corpus_root"]),
        limit=int(item.get("limit") or 100),
        focus_hint=item.get("focus_hint"),
        gold_directions=[[str(pid) for pid in group] for group in item.get("gold_directions") or []],
        papers=papers,
    )


def load_gold(path: str | Path) -> GoldDataset:
    return GoldDataset.load(path)

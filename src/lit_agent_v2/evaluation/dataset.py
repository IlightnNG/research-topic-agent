"""Evaluation dataset contracts for v2 S7."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path

__all__ = ["EvalCase", "EvalDataset", "load_dataset"]


@dataclass
class EvalCase:
    name: str
    topic_id: str
    corpus_root: str
    limit: int = 100
    focus_hint: str | None = None
    gold_directions: list[list[str]] = field(default_factory=list)
    gold_claims: list[str] = field(default_factory=list)


@dataclass
class EvalDataset:
    name: str
    version: str
    cases: list[EvalCase]
    sha: str = ""

    @classmethod
    def load(cls, path: str | Path) -> EvalDataset:
        raw = Path(path).read_bytes()
        data = json.loads(raw)
        cases = [
            EvalCase(
                name=str(item["name"]),
                topic_id=str(item["topic_id"]),
                corpus_root=str(item["corpus_root"]),
                limit=int(item.get("limit") or 100),
                focus_hint=item.get("focus_hint"),
                gold_directions=[list(map(str, group)) for group in item.get("gold_directions", [])],
                gold_claims=list(map(str, item.get("gold_claims", []))),
            )
            for item in data.get("cases", [])
        ]
        return cls(
            name=str(data.get("name") or "eval"),
            version=str(data.get("version") or "1"),
            cases=cases,
            sha=hashlib.sha256(raw).hexdigest()[:16],
        )

    def assert_frozen(self, expected_sha: str) -> None:
        if self.sha != expected_sha:
            raise RuntimeError(f"dataset changed: {self.sha} != {expected_sha}")


def load_dataset(path: str | Path) -> EvalDataset:
    return EvalDataset.load(path)

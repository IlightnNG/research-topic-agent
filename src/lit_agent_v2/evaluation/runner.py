"""Evaluation runner and parameter tuner for v2 S7/S8."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.domains.report.ingest import LocalCorpus
from lit_agent_v2.domains.report.map import MapService
from lit_agent_v2.domains.report.workflow import ReportWorkflow
from lit_agent_v2.evaluation.dataset import EvalCase, EvalDataset
from lit_agent_v2.evaluation.evaluators import EvalResult, evaluate
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database

__all__ = ["EvalRunner", "TuneConfig", "Tuner"]


@dataclass(frozen=True)
class TuneConfig:
    threshold: float = 0.35
    min_size: int = 3
    max_directions: int = 8


@dataclass
class EvalRunner:
    db: Database
    artifacts: ArtifactStore

    def run_case(self, case: EvalCase, config: TuneConfig) -> EvalResult:
        shell = RunShell(self.db, self.artifacts)
        outcome = ReportWorkflow(
            shell,
            LocalCorpus(case.corpus_root),
            mapper=MapService(
                threshold=config.threshold,
                min_size=config.min_size,
                max_directions=config.max_directions,
            ),
        ).run(
            RunRequest(
                topic_id=case.topic_id,
                limit=case.limit,
                focus_hint=case.focus_hint,
            )
        )
        return evaluate(
            case=case,
            mapping=outcome.mapping,
            words=outcome.draft.word_count,
            citations=1.0,
        )


@dataclass
class TuneResult:
    config: TuneConfig
    score: float
    metrics: dict[str, float] = field(default_factory=dict)
    seconds: float = 0.0


class Tuner:
    def __init__(self, db: Database, artifacts: ArtifactStore, dataset: EvalDataset) -> None:
        self.db = db
        self.artifacts = artifacts
        self.dataset = dataset
        self.runner = EvalRunner(db, artifacts)

    def evaluate(self, config: TuneConfig) -> TuneResult:
        started = time.monotonic()
        totals: dict[str, list[float]] = {}
        for case in self.dataset.cases:
            result = self.runner.run_case(case, config)
            for key, value in result.metrics.items():
                totals.setdefault(key, []).append(value)
        metrics = {
            key: round(sum(values) / len(values), 4)
            for key, values in totals.items()
            if values
        }
        words = metrics.get("report.words", 0.0)
        word_score = 1.0 if 1500 <= words <= 3000 else 0.5
        score = round(
            0.5 * metrics.get("directions.f1", 0.0)
            + 0.3 * metrics.get("report.citation_coverage", 0.0)
            + 0.2 * word_score,
            4,
        )
        elapsed = round(time.monotonic() - started, 2)
        self._record(config, score, metrics, elapsed)
        return TuneResult(config, score, metrics, elapsed)

    def search(self, configs: Iterable[TuneConfig], *, min_score: float = 0.0) -> list[TuneResult]:
        results = [self.evaluate(config) for config in configs]
        return sorted((item for item in results if item.score >= min_score), key=lambda item: -item.score)

    def _record(self, config: TuneConfig, score: float, metrics: dict[str, float], seconds: float) -> None:
        payload = json.dumps(config.__dict__, sort_keys=True)
        config_hash = hashlib.sha256(payload.encode()).hexdigest()[:16]
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO experiments(id,name,config_json,config_hash,dataset,score,"
                "hard_fail_json,status,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    uuid.uuid4().hex,
                    f"tune-{config_hash}",
                    payload,
                    config_hash,
                    self.dataset.name,
                    score,
                    json.dumps([]),
                    "complete",
                    datetime.now(UTC).isoformat(),
                ),
            )

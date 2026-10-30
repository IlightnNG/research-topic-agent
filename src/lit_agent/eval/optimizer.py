"""Experiment records and promotion policy (S19)."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine
from lit_agent.eval.report_eval import Comparison

__all__ = ["Experiment", "decide_promotion", "save_experiment"]


@dataclass
class Experiment:
    name: str
    config: dict[str, Any]
    dataset: str
    baseline_run_id: str | None = None
    candidates: list[str] | None = None
    score: float | None = None
    hard_fail: list[str] | None = None
    status: str = "pending"


def _hash(config: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()[:16]


def decide_promotion(
    comparison: Comparison,
    *,
    score_delta: float,
    min_score_delta: float = 0.02,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if comparison.hard_fail:
        reasons.append("hard metric regression")
    if comparison.regressions:
        reasons.append("regressions: " + ", ".join(comparison.regressions[:3]))
    if score_delta < min_score_delta:
        reasons.append(f"score delta {score_delta} < {min_score_delta}")
    return (not reasons, reasons)


def save_experiment(settings: Settings, experiment: Experiment) -> str:
    experiment_id = uuid.uuid4().hex
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text(
                    "INSERT INTO experiments"
                    "(id,name,hypothesis,config_json,config_hash,dataset,baseline_run_id,"
                    "candidates_json,score,hard_fail_json,status,created_at)"
                    " VALUES (:id,:name,:hyp,:cfg,:hash,:dataset,:baseline,:candidates,"
                    ":score,:hard,:status,:ts)"
                ),
                {
                    "id": experiment_id,
                    "name": experiment.name,
                    "hyp": None,
                    "cfg": json.dumps(experiment.config, ensure_ascii=False, default=str),
                    "hash": _hash(experiment.config),
                    "dataset": experiment.dataset,
                    "baseline": experiment.baseline_run_id,
                    "candidates": json.dumps(experiment.candidates or []),
                    "score": experiment.score,
                    "hard": json.dumps(experiment.hard_fail or []),
                    "status": experiment.status,
                    "ts": datetime.now(UTC).isoformat(),
                },
            )
    finally:
        engine.dispose()
    return experiment_id

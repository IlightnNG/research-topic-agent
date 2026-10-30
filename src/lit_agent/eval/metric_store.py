"""Metric/span persistence (Phase 3.4 / S16)."""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine
from lit_agent.eval.metric_catalog import CATALOG, MetricDef

__all__ = [
    "collect_report_points",
    "load_points",
    "record_point",
    "record_span",
    "seed_definitions",
    "span",
]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def seed_definitions(settings: Settings) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            for item in CATALOG.values():
                conn.execute(
                    text(
                        "INSERT INTO metric_definitions"
                        "(metric_id,version,domain,unit,direction,formula,target_json,owner,created_at)"
                        " VALUES (:id,:v,:d,:u,:dir,:f,:t,'system',:ts)"
                        " ON CONFLICT(metric_id) DO UPDATE SET"
                        " version=excluded.version, domain=excluded.domain, unit=excluded.unit,"
                        " direction=excluded.direction, formula=excluded.formula,"
                        " target_json=excluded.target_json"
                    ),
                    {
                        "id": item.metric_id,
                        "v": item.version,
                        "d": item.domain,
                        "u": item.unit,
                        "dir": item.direction,
                        "f": item.formula,
                        "t": json.dumps(item.target) if item.target else None,
                        "ts": _now(),
                    },
                )
    finally:
        engine.dispose()


def record_point(
    settings: Settings,
    metric_id: str,
    value: float | None,
    *,
    scope: str,
    scope_id: str,
    run_id: str | None = None,
    node_id: str | None = None,
    step: str | None = None,
    numerator: float | None = None,
    denominator: float | None = None,
    sample_size: int | None = None,
    config_hash: str | None = None,
    prompt_version: str | None = None,
    model: str | None = None,
    dataset: str | None = None,
) -> None:
    definition: MetricDef = CATALOG[metric_id]
    if denominator == 0:
        value = None
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text(
                    "INSERT INTO metric_points"
                    "(id,metric_id,metric_version,scope,scope_id,run_id,node_id,step,"
                    "value,numerator,denominator,sample_size,unit,config_hash,prompt_version,"
                    "model,dataset,ts) VALUES"
                    "(:id,:mid,:mv,:scope,:sid,:rid,:nid,:step,:value,:num,:den,:sample,"
                    ":unit,:cfg,:prompt,:model,:dataset,:ts)"
                ),
                {
                    "id": uuid.uuid4().hex,
                    "mid": metric_id,
                    "mv": definition.version,
                    "scope": scope,
                    "sid": scope_id,
                    "rid": run_id,
                    "nid": node_id,
                    "step": step,
                    "value": value,
                    "num": numerator,
                    "den": denominator,
                    "sample": sample_size,
                    "unit": definition.unit,
                    "cfg": config_hash,
                    "prompt": prompt_version,
                    "model": model,
                    "dataset": dataset,
                    "ts": _now(),
                },
            )
    finally:
        engine.dispose()


def record_span(
    settings: Settings,
    *,
    run_id: str,
    name: str,
    status: str,
    trace_id: str | None = None,
    parent_span_id: str | None = None,
    node_id: str | None = None,
    step: str | None = None,
    start_ts: str | None = None,
    end_ts: str | None = None,
    duration_ms: int | None = None,
    attributes: dict[str, Any] | None = None,
    error_code: str | None = None,
) -> str:
    span_id = uuid.uuid4().hex
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            conn.execute(
                text(
                    "INSERT INTO run_spans"
                    "(span_id,trace_id,parent_span_id,run_id,node_id,step,name,status,"
                    "start_ts,end_ts,duration_ms,attributes_json,error_code)"
                    " VALUES (:sid,:tid,:pid,:rid,:nid,:step,:name,:status,:start,:end,:ms,:attrs,:err)"
                ),
                {
                    "sid": span_id,
                    "tid": trace_id or run_id,
                    "pid": parent_span_id,
                    "rid": run_id,
                    "nid": node_id,
                    "step": step,
                    "name": name,
                    "status": status,
                    "start": start_ts or _now(),
                    "end": end_ts,
                    "ms": duration_ms,
                    "attrs": json.dumps(attributes or {}, ensure_ascii=False, default=str),
                    "err": error_code,
                },
            )
    finally:
        engine.dispose()
    return span_id


@contextmanager
def span(settings: Settings, *, run_id: str, name: str, **kwargs: Any) -> Iterator[str]:
    started = time.monotonic()
    span_id = record_span(settings, run_id=run_id, name=name, status="started", **kwargs)
    try:
        yield span_id
        record_span(
            settings,
            run_id=run_id,
            name=name,
            status="ok",
            duration_ms=int((time.monotonic() - started) * 1000),
            **{key: value for key, value in kwargs.items() if key in {"node_id", "step"}},
        )
    except Exception:
        record_span(
            settings,
            run_id=run_id,
            name=name,
            status="failed",
            duration_ms=int((time.monotonic() - started) * 1000),
            **{key: value for key, value in kwargs.items() if key in {"node_id", "step"}},
        )
        raise


def load_points(settings: Settings, run_id: str) -> list[dict[str, Any]]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            rows = conn.execute(
                text(
                    "SELECT metric_id,metric_version,scope,scope_id,node_id,step,value,"
                    "numerator,denominator,sample_size,unit,ts"
                    " FROM metric_points WHERE run_id = :rid ORDER BY ts, metric_id"
                ),
                {"rid": run_id},
            ).all()
    finally:
        engine.dispose()
    return [dict(row._mapping) for row in rows]


def collect_report_points(settings: Settings, run_id: str) -> None:
    """Derive core report metrics from the persisted report + llm_calls."""
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text(
                    "SELECT word_count,sections_json,claims_json,coverage,thin,"
                    "fallback_count,generated_by FROM reports WHERE run_id=:rid"
                    " ORDER BY created_at DESC LIMIT 1"
                ),
                {"rid": run_id},
            ).first()
            calls = conn.execute(
                text(
                    "SELECT COUNT(*), COALESCE(SUM(cache_hit),0),"
                    " COALESCE(SUM(CASE WHEN ok=0 THEN 1 ELSE 0 END),0)"
                    " FROM llm_calls WHERE run_id=:rid"
                ),
                {"rid": run_id},
            ).one()
    finally:
        engine.dispose()
    if row is None:
        return
    words, sections_json, claims_json, coverage, thin, fallback_count, generated_by = row
    sections = json.loads(sections_json or "[]")
    claims = json.loads(claims_json or "[]")
    total_calls, cache_hits, failures = calls
    record_point(settings, "report.words", float(words or 0), scope="run", scope_id=run_id, run_id=run_id)
    record_point(settings, "report.sections", float(len(sections)), scope="run", scope_id=run_id, run_id=run_id)
    record_point(
        settings,
        "report.coverage",
        float(coverage or 0),
        scope="run",
        scope_id=run_id,
        run_id=run_id,
        denominator=1.0,
    )
    record_point(
        settings,
        "report.fallback_rate",
        float(fallback_count or 0) / max(1, len(sections)),
        scope="run",
        scope_id=run_id,
        run_id=run_id,
        numerator=float(fallback_count or 0),
        denominator=float(max(1, len(sections))),
    )
    record_point(settings, "report.thin", 1.0 if thin else 0.0, scope="run", scope_id=run_id, run_id=run_id)
    record_point(
        settings,
        "report.cache_hit_rate",
        float(cache_hits) / total_calls if total_calls else None,
        scope="run",
        scope_id=run_id,
        run_id=run_id,
        numerator=float(cache_hits),
        denominator=float(total_calls),
    )
    record_point(settings, "llm.failures", float(failures), scope="run", scope_id=run_id, run_id=run_id)
    record_point(
        settings,
        "claim.citation_coverage",
        float(sum(1 for claim in claims if claim.get("citations"))) / max(1, len(claims)),
        scope="run",
        scope_id=run_id,
        run_id=run_id,
        numerator=float(sum(1 for claim in claims if claim.get("citations"))),
        denominator=float(max(1, len(claims))),
    )

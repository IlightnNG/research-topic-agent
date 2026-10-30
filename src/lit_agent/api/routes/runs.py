"""Run 详情 / 事件分页 / 报告 / SSE 流。"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy import text

from lit_agent.api.dependencies import get_engine, get_settings
from lit_agent.api.schemas import InjectRequest
from lit_agent.api.sse import event_stream
from lit_agent.config import Settings  # noqa: F401 - FastAPI 依赖注解需要
from lit_agent.db.repo import reports as report_repo
from lit_agent.db.session import connect
from lit_agent.errors import E_CONFIG_INVALID, E_FEATURE_DISABLED, E_NOT_FOUND, LitError
from lit_agent.runtime import control

router = APIRouter()


def _require(value: Any, label: str) -> Any:
    if value is None:
        raise LitError(E_NOT_FOUND, f"{label} 不存在", context={"missing": label})
    return value


@router.get("/{run_id}")
def get_run(run_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        row = _require(
            conn.execute(text("SELECT * FROM runs WHERE id = :id"), {"id": run_id}).first(),
            f"run {run_id}",
        )
    data = dict(row._mapping)
    data.pop("config_snapshot_json", None)
    return data


@router.get("/{run_id}/events")
def list_events(
    run_id: str,
    after_seq: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = conn.execute(
            text(
                "SELECT seq, ts, type, stage, agent, severity, dedupe_key, payload_json"
                " FROM run_events WHERE run_id = :rid AND seq > :after ORDER BY seq LIMIT :limit"
            ),
            {"rid": run_id, "after": after_seq, "limit": limit},
        ).all()
    items = [
        {
            "seq": row[0],
            "ts": row[1],
            "type": row[2],
            "stage": row[3],
            "agent": row[4],
            "severity": row[5],
            "dedupe_key": row[6],
            "payload": json.loads(row[7] or "{}"),
        }
        for row in rows
    ]
    return {"run_id": run_id, "after_seq": after_seq, "items": items, "count": len(items)}


@router.get("/{run_id}/report")
def get_report(run_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    with connect(engine) as conn:
        rows = report_repo.get_by_run(conn, run_id)
    if not rows:
        raise LitError(E_NOT_FOUND, f"run {run_id} 尚无报告", context={"run_id": run_id})
    row = rows[-1]
    data = dict(row._mapping)
    data["claims"] = json.loads(data.pop("claims_json", "null") or "[]")
    data.pop("metrics_snapshot_json", None)
    # Old reports (pre-3.2) may have null metadata.
    data["language"] = data.get("language") or "en"
    data["generated_by"] = data.get("generated_by") or "template"
    data["fallback_count"] = int(data.get("fallback_count") or 0)
    data["coverage"] = float(data.get("coverage") or 0.0)
    data["thin"] = bool(data.get("thin"))
    data["word_count"] = int(
        data.get("word_count") or len(str(data.get("content_md") or "").split())
    )
    # S12：分节以库里的 sections_json 为准；旧数据回落"一 claim 一节"
    stored = json.loads(data.pop("sections_json", "null") or "null")
    if stored:
        data["sections"] = stored
    else:
        data["sections"] = [
            {
                "id": f"claim-{index}",
                "title": f"Evidence {index + 1}",
                "body": claim.get("text", ""),
                "claim_indexes": [index],
                "kind": "findings",
            }
            for index, claim in enumerate(data["claims"])
        ]
    return data


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    request: Request,
    after_seq: int = Query(default=0, ge=0),
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    header_seq = request.headers.get("last-event-id")
    start = int(header_seq) if header_seq and header_seq.isdigit() else after_seq
    return StreamingResponse(
        event_stream(settings, run_id, after_seq=start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/{run_id}/abort")
def abort_run(run_id: str, engine: Any = Depends(get_engine)) -> dict[str, Any]:
    """S2：请求中止。真正退出发生在下一个阶段边界（control 标记）。"""
    with connect(engine) as conn:
        exists = conn.execute(text("SELECT 1 FROM runs WHERE id = :id"), {"id": run_id}).first()
    if exists is None:
        raise LitError(E_NOT_FOUND, f"run 不存在：{run_id}", context={"run_id": run_id})
    control.request_abort(run_id)
    return {"run_id": run_id, "abort_requested": True}


def _not_implemented(feature: str) -> JSONResponse:
    return JSONResponse(
        status_code=501,
        content={"code": E_FEATURE_DISABLED, "message": f"{feature} 在 Phase 3 实现",
                 "context": {"feature": feature}},
    )


def _require_run(engine: Any, run_id: str) -> dict[str, Any]:
    with connect(engine) as conn:
        row = conn.execute(
            text("SELECT id, state, topic_id FROM runs WHERE id = :id"), {"id": run_id}
        ).first()
    if row is None:
        raise LitError(E_NOT_FOUND, f"run 不存在：{run_id}", context={"run_id": run_id})
    return dict(row._mapping)


@router.post("/{run_id}/pause")
def pause_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> JSONResponse:
    """在**阶段边界**暂停：run 置 paused，checkpoint 保留，可 resume。"""
    run = _require_run(engine, run_id)
    if run["state"] != "running":
        raise LitError(
            E_CONFIG_INVALID,
            f"只有 running 的 run 可以暂停（当前 {run['state']}）",
            context={"run_id": run_id, "state": run["state"]},
        )
    control.request_pause(run_id)
    return JSONResponse(status_code=202, content={"run_id": run_id, "state": "pausing"})


@router.post("/{run_id}/resume")
def resume_run(
    run_id: str,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> JSONResponse:
    """从 paused 续跑（后台线程，checkpoint 续接）。"""
    import threading

    from lit_agent.runtime.graph_runner import run_graph

    run = _require_run(engine, run_id)
    if run["state"] != "paused":
        raise LitError(
            E_CONFIG_INVALID,
            f"只有 paused 的 run 可以续跑（当前 {run['state']}）",
            context={"run_id": run_id, "state": run["state"]},
        )
    control.clear_pause(run_id)
    threading.Thread(
        target=run_graph,
        kwargs={
            "settings": settings,
            "topic_id": str(run["topic_id"]),
            "run_id": run_id,
            "resume": True,
        },
        daemon=True,
        name=f"resume-{run_id}",
    ).start()
    return JSONResponse(status_code=202, content={"run_id": run_id, "state": "resuming"})


@router.post("/{run_id}/inject")
def inject_run(
    run_id: str,
    payload: InjectRequest,
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    """注入提示词：在下一个阶段边界合并进 `focus_hint`，并写 `inject` 事件。"""
    _require_run(engine, run_id)
    control.inject_prompt(run_id, payload.prompt)
    return {"run_id": run_id, "pending": len(control.pending_inject(run_id))}


@router.get("/{run_id}/metrics")
def get_metrics(
    run_id: str,
    settings: Settings = Depends(get_settings),
    engine: Any = Depends(get_engine),
) -> dict[str, Any]:
    """单 run 指标：优先读 `metrics` 表；缺失时按需计算（不要求回填迁移）。"""
    from lit_agent.eval.metrics import compute_run_metrics

    with connect(engine) as conn:
        exists = conn.execute(
            text("SELECT 1 FROM runs WHERE id = :rid"), {"rid": run_id}
        ).first()
        rows = conn.execute(
            text(
                "SELECT metric, value FROM metrics"
                " WHERE scope = 'run' AND scope_id = :rid"
            ),
            {"rid": run_id},
        ).all()
    if exists is None:
        raise LitError(E_NOT_FOUND, f"run 不存在：{run_id}", context={"run_id": run_id})

    if rows:
        payload = {str(metric): float(value) for metric, value in rows}
        source = "persisted"
    else:
        payload = compute_run_metrics(settings, run_id)
        source = "computed"

    # S5：把 duration_ms_<stage> 还原成前端友好的 duration_by_stage + slowest_stage
    durations = {
        key[len("duration_ms_") :]: float(value)
        for key, value in payload.items()
        if key.startswith("duration_ms_")
        and key != "duration_ms_total"
        and isinstance(value, (int, float))
    }
    if durations:
        payload["duration_by_stage"] = durations
        payload["slowest_stage"] = max(durations, key=durations.get)
    return {"run_id": run_id, "source": source, **payload}

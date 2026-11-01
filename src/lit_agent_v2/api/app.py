"""V2 API: asynchronous report runs, SSE, minimal Workflow timeline."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from lit_agent_v2.composition import (
    build_chat_service,
    build_event_reader,
    build_report_reader,
    build_report_workflow_from_path,
)
from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.domains.chat.answer import stream_reply
from lit_agent_v2.domains.chat.store import ChatStore
from lit_agent_v2.interface.router import build_platform_router
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database

__all__ = ["create_app"]


class RunBody(BaseModel):
    topic_id: str
    limit: int = Field(default=100, ge=1, le=100)
    focus_hint: str | None = None
    title: str | None = None


class ChatBody(BaseModel):
    topic_id: str
    message: str
    session_id: str | None = None


def _execute(
    shell: RunShell,
    corpus_root: Path,
    request: RunRequest,
    run_id: str,
    *,
    resume: bool = False,
) -> None:
    try:
        build_report_workflow_from_path(shell, corpus_root).run(
            request,
            run_id=run_id,
            resume=resume,
        )
    except Exception:
        # RunShell marks failed; keep the thread from printing a traceback.
        return


def create_app(
    *,
    db_path: str | Path | None = None,
    corpus_root: str | Path | None = None,
    chat_composer=None,
    platform_llm=None,
) -> FastAPI:
    db = Database(db_path or os.environ.get("LIT_V2_DB", "D:/lit-agent-store/v2/v2.sqlite"))
    db.migrate()
    artifacts = ArtifactStore(Path(db.path).parent / "artifacts")
    shell = RunShell(db, artifacts)
    corpus = Path(corpus_root or os.environ.get("LIT_V2_CORPUS", "D:/lit-agent-store/v2/corpus"))
    report_reader = build_report_reader(db)
    event_reader = build_event_reader(db)
    app = FastAPI(title="lit-agent-v2")
    app.include_router(
        build_platform_router(db, corpus_root=corpus, llm=platform_llm)
    )

    def error_response(status: int, code: str, message: str, **details: Any) -> JSONResponse:
        return JSONResponse(
            status_code=status,
            content={"error": {"code": code, "message": message, "details": details}},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = str(exc.detail) if str(exc.detail).startswith("E_") else "E_HTTP"
        return error_response(exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(422, "E_INVALID_REQUEST", "request validation failed", errors=exc.errors())

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
        return error_response(500, "E_INTERNAL", "internal error")

    @app.get("/api/v2/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "tables": len(db.table_names())}

    @app.post("/api/v2/runs", status_code=202)
    def create_run(body: RunBody) -> dict[str, Any]:
        if not corpus.exists():
            raise HTTPException(status_code=422, detail="E_CORPUS_NOT_FOUND")
        run_id = shell.prepare(
            RunRequest(topic_id=body.topic_id, limit=body.limit, focus_hint=body.focus_hint)
        )
        thread = threading.Thread(
            target=_execute,
            args=(
                shell,
                corpus,
                RunRequest(
                    topic_id=body.topic_id,
                    limit=body.limit,
                    focus_hint=body.focus_hint,
                ),
                run_id,
            ),
            daemon=True,
        )
        thread.start()
        return {"run_id": run_id, "state": "running", "events": f"/api/v2/runs/{run_id}/events"}

    @app.get("/api/v2/runs/{run_id}")
    def get_run(run_id: str) -> dict[str, Any]:
        row = shell.get_run(run_id)
        if row is None:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        return row

    def _events(run_id: str, last: int = 0) -> Iterator[str]:
        started = time.monotonic()
        while time.monotonic() - started < 120:
            rows = event_reader.after(run_id, last)
            run_row = shell.get_run(run_id)
            state = run_row["state"] if run_row else None
            for row in rows:
                last = int(row["seq"])
                data = {
                    "seq": row["seq"],
                    "type": row["type"],
                    "node_id": row["node_id"],
                    "payload": row["payload"],
                    "ts": row["ts"],
                }
                yield f"id: {last}\nevent: {row['type']}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
            if state in {"succeeded", "failed", "aborted"}:
                yield "event: stream.end\ndata: {}\n\n"
                return
            time.sleep(0.1)

    @app.post("/api/v2/runs/{run_id}/pause")
    def pause_run(run_id: str) -> dict[str, Any]:
        shell.pause(run_id)
        return {"run_id": run_id, "state": shell._state(run_id)}

    @app.post("/api/v2/runs/{run_id}/resume")
    def resume_run(run_id: str) -> dict[str, Any]:
        with db.connect() as conn:
            row = conn.execute(
                "SELECT request_json FROM runs WHERE id=?", (run_id,)
            ).fetchone()
        if row is None or not row[0]:
            raise HTTPException(status_code=404, detail="E_RUN_NOT_FOUND")
        payload = json.loads(row[0])
        shell.resume(run_id)
        thread = threading.Thread(
            target=_execute,
            args=(
                shell,
                corpus,
                RunRequest(
                    topic_id=payload["topic_id"],
                    limit=int(payload.get("limit") or 100),
                    focus_hint=payload.get("focus_hint"),
                ),
                run_id,
            ),
            kwargs={"resume": True},
            daemon=True,
        )
        thread.start()
        return {"run_id": run_id, "state": shell._state(run_id)}

    @app.post("/api/v2/runs/{run_id}/abort")
    def abort_run(run_id: str) -> dict[str, Any]:
        shell.abort(run_id)
        return {"run_id": run_id, "state": shell._state(run_id)}

    @app.get("/api/v2/runs/{run_id}/events")
    def run_events(
        run_id: str, last_event_id: str | None = Header(default=None, alias="Last-Event-ID")
    ) -> StreamingResponse:
        last = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        return StreamingResponse(_events(run_id, last), media_type="text/event-stream")

    chat_store = ChatStore(db)

    @app.post("/api/v2/chat")
    def chat(body: ChatBody) -> dict[str, Any]:
        session_id = body.session_id or chat_store.create(body.topic_id)
        chat_store.append(session_id, "user", body.message)
        reply = build_chat_service(corpus, composer=chat_composer).answer(
            topic_id=body.topic_id, message=body.message
        )
        chat_store.append(session_id, "assistant", reply.text, reply.citations)
        return {
            "session_id": session_id,
            "text": reply.text,
            "answered": reply.answered,
            "citations": reply.citations,
            "reason": reply.reason,
        }

    @app.get("/api/v2/chat/sessions/{session_id}")
    def chat_history(session_id: str) -> dict[str, Any]:
        return {"session_id": session_id, "messages": chat_store.history(session_id)}

    @app.get("/api/v2/chat/stream")
    def chat_stream(topic_id: str, message: str) -> StreamingResponse:
        reply = build_chat_service(corpus).answer(
            topic_id=topic_id, message=message
        )
        chunks = stream_reply(reply)

        def generate():
            for chunk in chunks:
                yield f"event: token.delta\ndata: {json.dumps(chunk, ensure_ascii=False)}\n\n"
            yield "event: stream.end\ndata: {}\n\n"

        return StreamingResponse(generate(), media_type="text/event-stream")

    @app.get("/api/v2/runs/{run_id}/report")
    def get_run_report(run_id: str) -> dict[str, Any]:
        report_id = report_reader.by_run(run_id)
        if report_id is None:
            raise HTTPException(status_code=404, detail="E_REPORT_NOT_FOUND")
        return {"run_id": run_id, "report_id": report_id}

    @app.get("/api/v2/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        payload = report_reader.get(report_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="E_REPORT_NOT_FOUND")
        return payload

    @app.get("/", response_class=HTMLResponse)
    def timeline() -> str:
        return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>lit-agent v2 report</title>
<style>
:root { color-scheme: light dark; font-family: system-ui, sans-serif; }
body { margin: 0; background: #f6f7f9; color: #111; }
main { max-width: 1100px; margin: 0 auto; padding: 28px 20px 80px; }
h1 { margin: 0 0 4px; font-size: 24px; }
.sub { color: #666; margin: 0 0 24px; }
.card { background: #fff; border: 1px solid #ddd; border-radius: 10px; padding: 18px; margin-bottom: 18px; }
form { display: flex; gap: 10px; flex-wrap: wrap; align-items: end; }
label { display: grid; gap: 4px; font-size: 12px; color: #555; }
input { padding: 8px 10px; border: 1px solid #bbb; border-radius: 6px; font: inherit; }
button { padding: 9px 16px; border: 0; border-radius: 6px; background: #111; color: #fff; cursor: pointer; }
button:disabled { opacity: .5; cursor: default; }
#status { font-size: 13px; color: #555; margin-top: 12px; }
#events { list-style: none; padding: 0; margin: 10px 0 0; max-height: 190px; overflow: auto; font: 12px ui-monospace, monospace; }
#events li { padding: 3px 0; border-bottom: 1px solid #eee; }
.section { border-top: 1px solid #eee; padding: 14px 0; }
.section h3 { margin: 0 0 8px; font-size: 17px; }
.section pre { white-space: pre-wrap; word-break: break-word; font: 13px/1.55 ui-monospace, monospace; margin: 0; }
#report-meta { color: #666; font-size: 13px; margin-bottom: 8px; }
.error { color: #a00; white-space: pre-wrap; }
</style></head><body><main>
<h1>Report Workflow</h1>
<p class="sub">Create a report run, watch sections stream in, then read the report.</p>
<section class="card">
<form id="run-form">
  <label>Topic<input id="topic" value="agents" required></label>
  <label>Limit<input id="limit" type="number" min="1" max="100" value="20"></label>
  <button id="run-button" type="submit">Run report</button>
</form>
<div id="status">Idle</div>
<ul id="events"></ul>
</section>
<section id="report-card" class="card" hidden>
  <h2 id="report-title">Report</h2>
  <div id="report-meta"></div>
  <p class="sub">Report sections</p>
  <div id="sections"></div>
</section>
</main>
<script>
const $ = (id) => document.getElementById(id);
const form = $('run-form');
let currentRun = null, timer = null, es = null;
function status(text) { $('status').textContent = text; }
function eventLine(text) {
  const li = document.createElement('li');
  li.textContent = text;
  $('events').appendChild(li);
  $('events').scrollTop = $('events').scrollHeight;
}
function stopWatch() {
  if (timer) { clearInterval(timer); timer = null; }
  if (es) { es.close(); es = null; }
}
async function loadReport(runId) {
  const link = await fetch(`/api/v2/runs/${runId}/report`);
  if (!link.ok) return;
  const { report_id } = await link.json();
  const response = await fetch(`/api/v2/reports/${report_id}`);
  if (!response.ok) return;
  const payload = await response.json();
  const report = payload.report || {};
  $('report-card').hidden = false;
  $('report-title').textContent = report.title || 'Report';
  $('report-meta').textContent = `${report.state || ''} · ${report.word_count || 0} words`;
  const host = $('sections');
  host.innerHTML = '';
  for (const section of payload.sections || []) {
    const block = document.createElement('article');
    block.className = 'section';
    const title = document.createElement('h3');
    title.textContent = section.title || section.section_id || 'Section';
    const body = document.createElement('pre');
    body.textContent = section.body || '';
    block.append(title, body);
    host.appendChild(block);
  }
  status('Report ready');
}
function watch(runId) {
  currentRun = runId;
  es = new EventSource(`/api/v2/runs/${runId}/events`);
  const types = ['run.started', 'run.paused', 'run.resumed', 'node.started', 'node.finished',
                 'node.failed', 'section.delta', 'run.finished', 'run.failed'];
  types.forEach((type) => es.addEventListener(type, (event) => {
    let data = {};
    try { data = JSON.parse(event.data || '{}'); } catch (_) {}
    eventLine(`${type}${data.node_id ? ' · ' + data.node_id : ''}${data.payload?.title ? ' · ' + data.payload.title : ''}`);
    if (type === 'section.delta' || type === 'run.finished') loadReport(runId);
  }));
  timer = setInterval(async () => {
    const response = await fetch(`/api/v2/runs/${runId}`);
    if (!response.ok) return;
    const run = await response.json();
    status(`Run ${run.state}`);
    if (['succeeded', 'failed', 'aborted'].includes(run.state)) {
      stopWatch();
      if (run.state === 'succeeded') loadReport(runId);
    }
  }, 1000);
}
form.addEventListener('submit', async (event) => {
  event.preventDefault();
  stopWatch();
  $('events').innerHTML = '';
  $('report-card').hidden = true;
  $('run-button').disabled = true;
  status('Starting…');
  try {
    const response = await fetch('/api/v2/runs', {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify({topic_id: $('topic').value, limit: Number($('limit').value)})
    });
    const payload = await response.json();
    if (!response.ok) {
      status('Request failed');
      eventLine(payload.error?.code || response.statusText);
      return;
    }
    status(`Run ${payload.run_id}`);
    watch(payload.run_id);
  } catch (error) {
    status('Network error');
    eventLine(String(error));
  } finally {
    $('run-button').disabled = false;
  }
});
</script></body></html>"""

    return app

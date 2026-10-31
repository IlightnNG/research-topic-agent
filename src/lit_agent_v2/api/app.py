"""V2 API: asynchronous report runs, SSE, minimal Workflow timeline."""

from __future__ import annotations

import json
import os
import threading
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from lit_agent_v2.composition import (
    build_chat_service,
    build_event_reader,
    build_report_reader,
    build_report_workflow_from_path,
)
from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.domains.chat.answer import stream_reply
from lit_agent_v2.domains.chat.store import ChatStore
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
) -> FastAPI:
    db = Database(db_path or os.environ.get("LIT_V2_DB", "D:/lit-agent-store/v2/v2.sqlite"))
    db.migrate()
    artifacts = ArtifactStore(Path(db.path).parent / "artifacts")
    shell = RunShell(db, artifacts)
    corpus = Path(corpus_root or os.environ.get("LIT_V2_CORPUS", "D:/lit-agent-store/v2/corpus"))
    report_reader = build_report_reader(db)
    event_reader = build_event_reader(db)
    app = FastAPI(title="lit-agent-v2")

    @app.get("/api/v2/health")
    def health() -> dict[str, Any]:
        return {"ok": True, "tables": len(db.table_names())}

    @app.post("/api/v2/runs", status_code=202)
    def create_run(body: RunBody) -> dict[str, Any]:
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
            raise HTTPException(status_code=404, detail="E_NOT_FOUND")
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
            raise HTTPException(status_code=404, detail="E_NOT_FOUND")
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
            raise HTTPException(status_code=404, detail="E_NOT_FOUND")
        return {"run_id": run_id, "report_id": report_id}

    @app.get("/api/v2/reports/{report_id}")
    def get_report(report_id: str) -> dict[str, Any]:
        payload = report_reader.get(report_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="E_NOT_FOUND")
        return payload

    @app.get("/", response_class=HTMLResponse)
    def timeline() -> str:
        return """<!doctype html><html><head><meta charset="utf-8">
<title>lit-agent v2</title></head><body>
<h1>Report Workflow</h1>
<form id="f"><label>topic <input id="topic" value="agents"></label>
<label>limit <input id="limit" type="number" value="20"></label>
<button>Run</button></form>
<pre id="out"></pre>
<script>
const out=document.getElementById('out');
document.getElementById('f').onsubmit=async (e)=>{
 e.preventDefault(); out.textContent='starting...';
 const r=await fetch('/api/v2/runs',{method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({topic_id:document.getElementById('topic').value,
   limit:Number(document.getElementById('limit').value)})});
 const j=await r.json(); out.textContent=JSON.stringify(j,null,2)+'\\n';
 const es=new EventSource(j.events);
 ['run.started','node.started','node.finished','node.failed','run.finished'].forEach(t=>
   es.addEventListener(t,e=>{out.textContent+=`${t}: ${e.data}\\n`;}));
 es.addEventListener('stream.end',()=>{es.close();out.textContent+='done\\n';});
};
</script></body></html>"""

    return app

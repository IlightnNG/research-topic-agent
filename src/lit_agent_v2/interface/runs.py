"""Platform run service: one report Node through WorkflowRunner/Kernel/Tools."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from lit_agent_v2.contracts.node import WorkflowDefinition
from lit_agent_v2.contracts.report import ReportDraft, Section
from lit_agent_v2.kernel.agent.checkpoint import FileCheckpointStore
from lit_agent_v2.kernel.agent.node import KernelNodeAdapter
from lit_agent_v2.kernel.llm import DeepSeekChatClient, load_llm_config
from lit_agent_v2.kernel.node.loop import Kernel
from lit_agent_v2.kernel.node.ports import CheckpointPort, EventPort
from lit_agent_v2.storage.db import Database
from lit_agent_v2.storage.report_store import ReportStore
from lit_agent_v2.tools.packs.claims import build_claim_tools
from lit_agent_v2.tools.packs.corpus import build_corpus_tools
from lit_agent_v2.tools.packs.demo import build_demo_tools
from lit_agent_v2.tools.packs.report import build_report_tools
from lit_agent_v2.tools.packs.report_v2 import assemble_sections, finalize_report, write_one_section
from lit_agent_v2.tools.registry import ToolRegistry
from lit_agent_v2.verify.verdict import Verifier
from lit_agent_v2.workflow.events import EventLog
from lit_agent_v2.workflow.node.definition import build_report_demo_workflow
from lit_agent_v2.workflow.node.runner import WorkflowRunner
from lit_agent_v2.workflow.node.state import WorkflowInterrupted
from lit_agent_v2.workflow.report_v2 import build_report_v2_workflow
from lit_agent_v2.workflow.report_v2_runtime import build_report_v2_runtime

from .topics import TopicStore

__all__ = ["PlatformRunService"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


class DbEvents(EventPort):
    def __init__(self, db: Database, run_id: str) -> None:
        self.db = db
        self.run_id = run_id
        self.log = EventLog(db, run_id)

    def emit(self, event_type: str, *, node_id: str | None = None, **payload: Any) -> None:
        self.log.emit(event_type, node_id=node_id, **payload)
        state_by_event = {
            "node.started": "running",
            "node.verifying": "verifying",
            "node.committed": "committed",
            "node.degraded": "degraded",
            "node.skipped": "skipped",
            "node.failed": "failed",
        }
        if event_type == "run.failed":
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE run_nodes SET state='failed', error_code=?, finished_at=?"
                    " WHERE run_id=? AND state IN ('running','verifying','pending')",
                    (str(payload.get("error") or "run failed")[:2000], _now(), self.run_id),
                )
        state = state_by_event.get(event_type)
        if node_id and state:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE run_nodes SET state=?, finished_at=? WHERE run_id=? AND node_id=?",
                    (
                        state,
                        _now() if state in {"committed", "degraded", "skipped", "failed"} else None,
                        self.run_id,
                        node_id,
                    ),
                )


class DbNodeStore:
    def __init__(self, db: Database, events: DbEvents) -> None:
        self.db = db
        self.events = events

    def state(self, run_id: str, node_id: str) -> str | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT state FROM run_nodes WHERE run_id=? AND node_id=?",
                (run_id, node_id),
            ).fetchone()
        return str(row["state"]) if row else None

    def load_output(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM run_artifacts"
                " WHERE run_id=? AND node_id=? AND kind='output'"
                " ORDER BY created_at DESC LIMIT 1",
                (run_id, node_id),
            ).fetchone()
        return _loads(row["payload_json"], None) if row else None

    def commit(
        self, run_id: str, node_id: str, output: dict[str, Any], verdict: Any
    ) -> None:
        payload = _json(output)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE run_nodes SET state='committed', artifact_sha=?, finished_at=?,"
                " checkpoint_json=? WHERE run_id=? AND node_id=?",
                (digest, _now(), _json(verdict.to_dict()), run_id, node_id),
            )
            conn.execute(
                "INSERT OR REPLACE INTO run_artifacts"
                "(run_id,node_id,kind,sha256,payload_json,created_at)"
                " VALUES (?,?,?,?,?,?)",
                (run_id, node_id, "output", digest, payload, _now()),
            )

    def degrade(self, run_id: str, node_id: str, reason: str) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE run_nodes SET state='degraded', error_code=?, finished_at=?"
                " WHERE run_id=? AND node_id=?",
                (reason[:200], _now(), run_id, node_id),
            )


class DbCheckpoints(CheckpointPort):
    def __init__(self, db: Database) -> None:
        self.db = db

    def save(self, run_id: str, node_id: str, checkpoint: dict[str, Any]) -> None:
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE run_nodes SET checkpoint_json=? WHERE run_id=? AND node_id=?",
                (_json(checkpoint), run_id, node_id),
            )

    def load(self, run_id: str, node_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT checkpoint_json FROM run_nodes WHERE run_id=? AND node_id=?",
                (run_id, node_id),
            ).fetchone()
        return _loads(row["checkpoint_json"], None) if row else None


class PlatformRunService:
    def __init__(
        self,
        db: Database,
        *,
        corpus_root: Path,
        llm: Any | None = None,
    ) -> None:
        self.db = db
        self.corpus_root = Path(corpus_root)
        self.llm = llm
        self.topics = TopicStore(db)
        self.workflow_mode = os.environ.get("LIT_V2_WORKFLOW") or os.environ.get("LIT_V2_DEMO_CHAIN") or "report-v2"
        self._threads: dict[str, threading.Thread] = {}
        self._pause_events: dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def create(
        self,
        *,
        topic_id: str,
        focus_hint: str | None,
        language: str,
        limit: int = 20,
        source_mode: str = "local",
        query: str | None = None,
    ) -> dict[str, Any]:
        topic = self.topics.get(topic_id)
        if topic is None:
            raise ValueError("E_TOPIC_NOT_FOUND")
        if not self.corpus_root.exists():
            raise ValueError("E_CORPUS_NOT_FOUND")
        run_id = f"run-{uuid.uuid4().hex[:12]}"
        out_dir = str(
            Path(os.environ.get("LIT_V2_DEMO_OUT", "D:/lit-agent-store/v2-demo")) / run_id
        )
        workflow = self._workflow(topic, focus_hint, language)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO runs"
                "(id,topic_id,workflow,request_json,state,created_at,started_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (
                    run_id,
                    topic_id,
                    "report-demo",
                    _json(
                        {
                            "topic_id": topic_id,
                            "focus_hint": focus_hint,
                            "language": language,
                            "limit": limit,
                            "source_mode": source_mode,
                            "query": query or focus_hint,
                            "root": str(self.corpus_root),
                            "out_dir": out_dir,
                        }
                    ),
                    "running",
                    _now(),
                    _now(),
                ),
            )
            for node in workflow.nodes:
                conn.execute(
                    "INSERT OR IGNORE INTO run_nodes(run_id,node_id,state,attempt)"
                    " VALUES (?,?,?,0)",
                    (run_id, node.id, "pending"),
                )
        pause_event = threading.Event()
        with self._lock:
            self._pause_events[run_id] = pause_event
            thread = threading.Thread(
                target=self._run,
                args=(run_id, topic_id, focus_hint, language, workflow, out_dir, False),
                daemon=True,
            )
            self._threads[run_id] = thread
        thread.start()
        return self.get(run_id) or {}

    def _workflow(
        self, topic: dict[str, Any], focus_hint: str | None, language: str
    ) -> WorkflowDefinition:
        if self.workflow_mode in {"report-v2", "v2"}:
            return build_report_v2_workflow()
        base = build_report_demo_workflow()
        node = base.nodes[0]
        brief = self.topics.brief(str(topic["id"])) or {}
        scope = brief.get("scope_statement") or topic.get("direction")
        goal = (
            f"{node.goal}\n\n"
            f"TOPIC SCOPE: {scope}\n"
            f"INCLUDE: {brief.get('include_criteria', [])}\n"
            f"EXCLUDE: {brief.get('exclude_criteria', [])}\n"
            f"RUN FOCUS: {focus_hint or 'Use the topic direction as the only focus.'}\n"
            f"REPORT LANGUAGE: {'Chinese' if language == 'zh' else 'English'}\n"
            "Stay inside the topic scope. Do not introduce unrelated fields."
        )
        return WorkflowDefinition(
            name=base.name,
            version=base.version,
            nodes=(dataclasses.replace(node, goal=goal),),
            features=base.features,
        )

    def _run(
        self,
        run_id: str,
        topic_id: str,
        focus_hint: str | None,
        language: str,
        workflow: WorkflowDefinition,
        out_dir: str | None = None,
        resume: bool = False,
    ) -> None:
        events = DbEvents(self.db, run_id)
        events.emit("run.resumed" if resume else "run.started")
        with self.db.connect() as conn:
            run_row = conn.execute("SELECT request_json FROM runs WHERE id=?", (run_id,)).fetchone()
        run_request = _loads(run_row["request_json"], {}) if run_row else {}
        try:
            llm = self.llm or DeepSeekChatClient(load_llm_config())
            def should_stop() -> bool:
                return bool(
                    self._pause_events.get(run_id, threading.Event()).is_set()
                    or self._state(run_id) != "running"
                )
            final_key = "report.generate"
            if self.workflow_mode in {"report-v2", "v2"}:
                runtime = build_report_v2_runtime(llm)
                adapter = KernelNodeAdapter(
                    llm,
                    runtime,
                    workspace=out_dir or str(self.corpus_root),
                    events=events,
                    checkpoints=FileCheckpointStore(
                        Path(out_dir or "D:/lit-agent-store/v2-demo") / "checkpoints"
                    ),
                    should_stop=should_stop,
                )
                store = DbNodeStore(self.db, events)
                runner = WorkflowRunner(
                    kernel=adapter,
                    verifier=Verifier(),
                    store=store,
                    events=events,
                    control=lambda: self._state(run_id),
                )
                final_key = "report.audit_finalize"
            else:
                registry = ToolRegistry(
                    build_corpus_tools()
                    + build_claim_tools()
                    + build_report_tools(llm, language=language)
                    + build_demo_tools(llm)
                )
                kernel = Kernel(
                    llm,
                    registry,
                    checkpoint_store=DbCheckpoints(self.db),
                    events=events,
                    should_stop=should_stop,
                )
                store = DbNodeStore(self.db, events)
                runner = WorkflowRunner(
                    kernel=kernel,
                    verifier=Verifier(),
                    store=store,
                    events=events,
                    control=lambda: self._state(run_id),
                )
            outputs = runner.run(
                workflow,
                run_id=run_id,
                inputs={
                    "request": {
                        "root": str(self.corpus_root),
                        "topic_id": topic_id,
                        "focus_hint": focus_hint,
                        "language": language,
                        "limit": int(run_request.get("limit", 20)),
                        "source_mode": str(run_request.get("source_mode", "local")),
                        "query": run_request.get("query"),
                        "out_dir": out_dir,
                    }
                },
                resume=resume,
            )
            output = outputs.get(final_key, {})
            if not output.get("content_md") and not output.get("report_path"):
                raise RuntimeError("report node returned no content_md or report_path")
            report_id = self._persist_report(run_id, topic_id, output)
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE runs SET state='succeeded', finished_at=? WHERE id=?",
                    (_now(), run_id),
                )
            events.emit("run.finished", state="succeeded", report_id=report_id)
        except WorkflowInterrupted:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE run_nodes SET state='paused' WHERE run_id=? AND state IN ('running','verifying')",
                    (run_id,),
                )
                conn.execute("UPDATE runs SET state='paused' WHERE id=?", (run_id,))
            events.emit("run.paused", checkpoint=self._checkpoint(run_id))
        except Exception as exc:  # noqa: BLE001
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE runs SET state='failed', finished_at=?, error_code=? WHERE id=?",
                    (_now(), type(exc).__name__, run_id),
                )
            events.emit("run.failed", error=f"{type(exc).__name__}: {exc}")
        finally:
            with self._lock:
                self._threads.pop(run_id, None)
            self._pause_events.pop(run_id, None)

    def retry_section(self, run_id: str, section_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        request = _loads(row["request_json"], {})
        out_dir = Path(str(request.get("out_dir") or ""))
        topic_id = str(row["topic_id"])
        if not out_dir.exists():
            raise ValueError("E_RUN_OUTPUT_MISSING")
        llm = self.llm or DeepSeekChatClient(load_llm_config())
        plan_path = out_dir / "plan.json"
        evidence_path = out_dir / "evidence.json"
        if not plan_path.exists() or not evidence_path.exists():
            raise ValueError("E_SECTION_ARTIFACTS_MISSING")
        result = write_one_section(
            str(plan_path),
            section_id,
            str(evidence_path),
            str(out_dir),
            llm=llm,
        )
        if not result.get("ok"):
            raise ValueError("E_SECTION_RETRY_FAILED")
        draft = assemble_sections(str(plan_path), str(evidence_path), str(out_dir))
        final = finalize_report(
            str(draft["draft_path"]),
            str(evidence_path),
            str(out_dir),
            strict_quality=True,
            llm=llm,
            strict_audit=True,
        )
        report_id = self._persist_report(run_id, topic_id, final)
        with self.db.connect() as conn:
            conn.execute(
                "UPDATE runs SET state='succeeded', finished_at=?, error_code=NULL WHERE id=?",
                (_now(), run_id),
            )
        events = DbEvents(self.db, run_id)
        events.emit("section.retried", section_id=section_id, report_id=report_id)
        events.emit("run.finished", state="succeeded", report_id=report_id)
        return self.get(run_id)

    def _persist_report(
        self, run_id: str, topic_id: str, output: dict[str, Any]
    ) -> str:
        report_path = output.get("report_path")
        if report_path and Path(str(report_path)).exists():
            payload = json.loads(Path(str(report_path)).read_text(encoding="utf-8"))
            output = payload
        title = str(output.get("title") or "Report")
        content = str(output.get("content_md") or "")
        claims = []
        for claim in output.get("claims") or []:
            if not isinstance(claim, dict):
                continue
            normalized = dict(claim)
            normalized.setdefault("text", normalized.get("quote", ""))
            normalized.setdefault("quote", normalized.get("text", ""))
            normalized.setdefault("paper_id", "")
            normalized.setdefault("claim_id", f"C{len(claims) + 1}")
            claims.append(normalized)
        index_by_id = {str(claim.get("claim_id")): index for index, claim in enumerate(claims)}
        sections: list[Section] = []
        for item in output.get("sections") or []:
            if not isinstance(item, dict):
                continue
            body = str(item.get("body") or "")
            ids = re.findall(r"\[C(\d+)\]", body)
            sections.append(
                Section(
                    section_id=str(item.get("section_id") or f"section_{len(sections) + 1}"),
                    kind=str(item.get("kind") or "report"),
                    title=str(item.get("title") or "Section"),
                    body=body,
                    claim_indexes=[
                        index_by_id[f"C{claim_id}"]
                        for claim_id in ids
                        if f"C{claim_id}" in index_by_id
                    ],
                )
            )
        if not sections:
            sections = [
                Section(
                    section_id="report",
                    kind="report",
                    title=title,
                    body=content,
                    claim_indexes=list(range(len(claims))),
                )
            ]
        draft = ReportDraft(
            title=title,
            content_md=content,
            content_sha=hashlib.sha256(content.encode("utf-8")).hexdigest(),
            sections=sections,
            word_count=len(content.split()),
            claims=claims,
            state=str(output.get("state") or "complete"),
        )
        report_id = ReportStore(self.db).save(run_id=run_id, topic_id=topic_id, draft=draft)
        quality = output.get("quality")
        if quality is not None:
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE reports SET metrics_json=? WHERE report_id=?",
                    (_json(quality), report_id),
                )
        return report_id

    def _state(self, run_id: str) -> str:
        with self.db.connect() as conn:
            row = conn.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
        return str(row["state"]) if row else "failed"

    def _checkpoint(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute(
                "SELECT node_id,checkpoint_json FROM run_nodes"
                " WHERE run_id=? AND checkpoint_json IS NOT NULL ORDER BY rowid DESC LIMIT 1",
                (run_id,),
            ).fetchone()
        if not row:
            return None
        checkpoint = _loads(row["checkpoint_json"], {}) or {}
        return {
            "node_id": row["node_id"],
            "step": checkpoint.get("step", 0),
            "created_at": _now(),
        }

    def list_runs(self, topic_id: str) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM runs WHERE topic_id=? ORDER BY created_at DESC",
                (topic_id,),
            ).fetchall()
        return [self._run_payload(row) for row in rows]

    def get(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return self._run_payload(row) if row else None

    def _run_payload(self, row: Any) -> dict[str, Any]:
        request = _loads(row["request_json"], {})
        with self.db.connect() as conn:
            report = conn.execute(
                "SELECT report_id FROM reports WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
                (row["id"],),
            ).fetchone()
        return {
            "id": row["id"],
            "topic_id": row["topic_id"],
            "state": row["state"],
            "language": request.get("language", "en"),
            "focus_hint": request.get("focus_hint"),
            "report_id": report["report_id"] if report else None,
            "last_checkpoint": self._checkpoint(str(row["id"])),
            "created_at": row["created_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    def trace(self, run_id: str) -> dict[str, Any]:
        with self.db.connect() as conn:
            run_row = conn.execute("SELECT state FROM runs WHERE id=?", (run_id,)).fetchone()
            nodes = conn.execute(
                "SELECT node_id,state,started_at,finished_at,error_code FROM run_nodes"
                " WHERE run_id=? ORDER BY rowid",
                (run_id,),
            ).fetchall()
            events = conn.execute(
                "SELECT seq,type,node_id,payload_json,ts FROM run_events"
                " WHERE run_id=? ORDER BY seq",
                (run_id,),
            ).fetchall()
        normalized_events: list[dict[str, Any]] = []
        current_node: str | None = None
        for row in events:
            event_type = str(row["type"])
            node_id = row["node_id"]
            if event_type == "node.started" and node_id:
                current_node = str(node_id)
            # Older rows recorded context.compacted as a run-level event. It
            # belongs to the node that was executing at that point.
            if event_type == "context.compacted" and not node_id and current_node:
                node_id = current_node
            normalized_events.append(
                {
                    "id": f"{run_id}:{row['seq']}",
                    "type": event_type,
                    "node_id": node_id,
                    "ts": row["ts"],
                    **_loads(row["payload_json"], {}),
                }
            )
        return {
            "run_id": run_id,
            "nodes": [
                {
                    "node_id": row["node_id"],
                    "title": row["node_id"].replace(".", " ").title(),
                    "status": (
                        "failed"
                        if row["state"] in {"running", "verifying", "pending"}
                        and run_row is not None
                        and run_row["state"] == "failed"
                        else row["state"]
                    ),
                    "started_at": row["started_at"],
                    "finished_at": row["finished_at"],
                    "error": row["error_code"],
                }
                for row in nodes
            ],
            "events": normalized_events,
            "checkpoint": self._checkpoint(run_id),
        }

    def pause(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state='paused' WHERE id=? AND state='running'", (run_id,))
        with self._lock:
            event = self._pause_events.get(run_id)
        if event is not None:
            event.set()
        return self.get(run_id)

    def resume(self, run_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if row is None:
            return None
        with self._lock:
            thread = self._threads.get(run_id)
            event = self._pause_events.get(run_id)
        if thread is not None and thread.is_alive():
            # A pause request must not spawn a second worker. Let the active
            # worker continue from its next step.
            if event is not None:
                event.clear()
            with self.db.connect() as conn:
                conn.execute("UPDATE runs SET state='running' WHERE id=?", (run_id,))
            return self.get(run_id)
        if thread is not None:
            thread.join(timeout=0.2)
            if thread.is_alive():
                return self.get(run_id)
        if event is None:
            event = threading.Event()
            with self._lock:
                self._pause_events[run_id] = event
        event.clear()
        request = _loads(row["request_json"], {})
        topic = self.topics.get(row["topic_id"])
        if topic is None:
            return None
        workflow = self._workflow(topic, request.get("focus_hint"), request.get("language", "en"))
        with self.db.connect() as conn:
            conn.execute("UPDATE runs SET state='running' WHERE id=?", (run_id,))
        with self._lock:
            thread = threading.Thread(
                target=self._run,
                args=(
                    run_id,
                    row["topic_id"],
                    request.get("focus_hint"),
                    request.get("language", "en"),
                    workflow,
                    request.get("out_dir"),
                    True,
                ),
                daemon=True,
            )
            self._threads[run_id] = thread
        thread.start()
        return self.get(run_id)

    def delete(self, run_id: str) -> bool:
        with self.db.connect() as conn:
            exists = conn.execute("SELECT 1 FROM runs WHERE id=?", (run_id,)).fetchone()
            if not exists:
                return False
            conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
            conn.execute("DELETE FROM run_nodes WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM run_artifacts WHERE run_id=?", (run_id,))
            conn.execute("DELETE FROM run_events WHERE run_id=?", (run_id,))
            reports = conn.execute("SELECT report_id FROM reports WHERE run_id=?", (run_id,)).fetchall()
            for report in reports:
                conn.execute("DELETE FROM report_sections WHERE report_id=?", (report["report_id"],))
                conn.execute("DELETE FROM citations WHERE report_id=?", (report["report_id"],))
            conn.execute("DELETE FROM reports WHERE run_id=?", (run_id,))
        return True

    def paper(self, paper_id: str) -> dict[str, Any] | None:
        path = self.corpus_root / "papers.jsonl"
        if not path.exists():
            return None
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            paper = json.loads(line)
            if str(paper.get("paper_id")) == paper_id:
                return {
                    "id": paper_id,
                    "title": paper.get("title", ""),
                    "authors": paper.get("authors", []),
                    "year": paper.get("year"),
                    "venue": paper.get("venue", ""),
                    "abstract": paper.get("abstract", ""),
                    "source_url": paper.get("url") or paper.get("html_url") or "",
                    "pdf_url": paper.get("pdf_url") or "",
                }
        return None

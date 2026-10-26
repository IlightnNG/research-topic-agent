"""Phase 1.1 出口验证器（F1）。

10 条断言，输出红绿表；`--online` 额外跑真实 arXiv 数据（抓取→报告→三库对账）。
退出码：全部 PASS → 0；任一 FAIL → 1（可接进 CI）。

纪律：本脚本**只读或写临时目录**（默认 `D:/lit-agent-store/temp/verify-p1`），
绝不触碰 `config/config.yaml` 指向的真实库。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import text

from lit_agent.config import LoggingSettings, Settings, StorageSettings
from lit_agent.db.repo import papers as paper_repo
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine, upgrade_database
from lit_agent.errors import LitError
from lit_agent.models.paper import Paper
from lit_agent.models.topic import Topic
from lit_agent.runtime import jobs
from lit_agent.runtime.runner import run_topic
from lit_agent.stores.rebuild import rebuild_graph, rebuild_vector, verify_counts
from lit_agent.stores.vector import HashingEmbedder

DEFAULT_ROOT = "D:/lit-agent-store/temp/verify-p1"
ARXIV_SELECTOR = {"categories": ["cs.AI"], "query": "llm agent"}


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    seconds: float = 0.0


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, seconds: float = 0.0) -> None:
        self.results.append(Result(name, ok, detail, seconds))

    @property
    def ok(self) -> bool:
        return all(item.ok for item in self.results)

    def emit(self, path: Path | None = None) -> None:
        width = max(len(item.name) for item in self.results)
        print("\nPhase 1.1 exit verification")
        print("-" * (width + 60))
        for item in self.results:
            flag = "PASS" if item.ok else "FAIL"
            print(f"[{flag}] {item.name.ljust(width)}  {item.detail}  ({item.seconds:.1f}s)")
        print("-" * (width + 60))
        print(f"TOTAL: {sum(1 for r in self.results if r.ok)}/{len(self.results)} PASS")
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "ok": self.ok,
                        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "results": [
                            {"name": r.name, "ok": r.ok, "detail": r.detail, "seconds": r.seconds}
                            for r in self.results
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"report: {path}")


def _settings(root: Path) -> Settings:
    return Settings(
        storage=StorageSettings(data_root=str(root / "data")),
        logging=LoggingSettings(console=False),
    )


def _seed(settings: Settings, *, papers: int = 2, source: str | None = None) -> None:
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(
                conn, Topic(id="ai-agents", name="AI Agents", scope_statement="llm agents")
            )
            if source:
                topic_repo.upsert_sources(conn, "ai-agents", [(source, ARXIV_SELECTOR)])
            if papers:
                paper_repo.upsert_many(
                    conn,
                    [
                        Paper(
                            paper_id=f"arxiv:offline{index}",
                            title=f"Offline Paper {index}",
                            abstract="agents use tools and planning",
                            source="arxiv",
                            year=2025,
                        )
                        for index in range(papers)
                    ],
                )
    finally:
        engine.dispose()


def _paper_count(settings: Settings) -> int:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return int(conn.execute(text("SELECT COUNT(*) FROM papers")).scalar_one())
    finally:
        engine.dispose()


def _report_sha(settings: Settings, run_id: str) -> str | None:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return conn.execute(
                text("SELECT content_sha FROM reports WHERE run_id = :rid"), {"rid": run_id}
            ).scalar_one_or_none()
    finally:
        engine.dispose()


def _scalars(settings: Settings, sql: str) -> tuple[Any, ...]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            return tuple(conn.execute(text(sql)).one())
    finally:
        engine.dispose()


# --------------------------------------------------------------------------- #
# 断言
# --------------------------------------------------------------------------- #
def check_structure(settings: Settings) -> str:
    from lit_agent import structure

    root = Path(__file__).resolve().parents[1]
    src_root = root / "src" / "lit_agent"
    missing = structure.missing_files(src_root)
    missing += [rel for rel in structure.ROOT_FILES if not (root / rel).is_file()]
    total = len(structure.expected_files()) + len(structure.ROOT_FILES)
    if missing:
        raise AssertionError(f"missing {len(missing)}: {missing[:5]}")
    return f"{total - len(missing)}/{total} present"


def check_schema(settings: Settings) -> str:
    from lit_agent.db.session import verify_schema

    upgrade_database(settings)
    upgrade_database(settings)  # 幂等
    engine = make_engine(settings)
    try:
        status = verify_schema(engine)
    finally:
        engine.dispose()
    if status.get("missing_tables") or status.get("missing_columns"):
        raise AssertionError(f"schema drift: {status}")
    return f"tables={status.get('tables', 24)} schema={status.get('schema_version', '1.0')}"


def check_events(settings: Settings) -> str:
    from lit_agent.models.event import EventType
    from lit_agent.models.run import RunState
    from lit_agent.runtime.events import SqliteEventLog

    jobs.start(settings, "ai-agents", run_id="verify-events")
    engine = make_engine(settings)
    try:
        log = SqliteEventLog(engine, "verify-events")
        for index in range(3):
            log.emit(EventType.PHASE_CHANGE, stage=f"s{index}")
    finally:
        engine.dispose()
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            values = [
                int(row[0])
                for row in conn.execute(
                    text("SELECT seq FROM run_events WHERE run_id='verify-events' ORDER BY seq")
                ).all()
            ]
    finally:
        engine.dispose()
    jobs.finish(settings, "verify-events", state=RunState.ABORTED)
    if values != [1, 2, 3]:
        raise AssertionError(f"seq not contiguous: {values}")
    return "seq 1..3 contiguous"


def check_guards(settings: Settings) -> str:
    from lit_agent.graph.guards import NoProgressGuard
    from lit_agent.runtime.budget import RunBudget

    guard = NoProgressGuard(no_progress_steps=2)
    verdicts = [guard.check({"produced": value}) for value in (1, 1, 1)]
    if verdicts[-1] is None:
        raise AssertionError("停滞后应触发告警")
    budget = RunBudget(limit_usd=0.01)
    budget.add(cost_usd=0.02)
    if budget.check() != "stop":
        raise AssertionError("超预算应为 stop")
    return "no-progress warns; budget stops"


def check_runner_offline(settings: Settings) -> str:
    result = run_topic(settings, "ai-agents", run_id="verify-run-1")
    if result["state"] != "succeeded":
        raise AssertionError(f"run failed: {result.get('failure_report')}")
    expected = ["intake", "ingest", "curate", "report"]
    if list(result["stages"]) != expected:
        raise AssertionError(f"stages: {list(result['stages'])}")
    digest = _report_sha(settings, "verify-run-1")
    if not digest:
        raise AssertionError("报告未落库")
    metrics = result["budget"]
    return f"stages={expected} sha={digest} budget={metrics['state']}"


def check_idempotent(settings: Settings) -> str:
    before = _paper_count(settings)
    run_topic(settings, "ai-agents", run_id="verify-run-2")
    after = _paper_count(settings)
    sha1 = _report_sha(settings, "verify-run-1")
    sha2 = _report_sha(settings, "verify-run-2")
    if after != before:
        raise AssertionError(f"papers grew: {before} -> {after}")
    if sha1 != sha2:
        raise AssertionError(f"report sha differs: {sha1} vs {sha2}")
    return f"papers stable at {after}; sha identical"


def check_lock(settings: Settings) -> str:
    jobs.start(settings, "ai-agents", run_id="verify-lock")
    try:
        try:
            jobs.start(settings, "ai-agents", run_id="verify-lock-2")
        except LitError as exc:
            if exc.code != "E_LOCK_HELD":
                raise
        else:
            raise AssertionError("第二个 run 应被锁拒绝")
    finally:
        jobs.finish(
            settings,
            "verify-lock",
            state=__import__("lit_agent.models.run", fromlist=["RunState"]).RunState.ABORTED,
        )
    return "E_LOCK_HELD on concurrent run"


def check_stores(settings: Settings) -> str:
    rebuild_graph(settings)
    rebuild_vector(settings, embedder=HashingEmbedder())
    report = verify_counts(settings, embedder=HashingEmbedder())
    if not report["ok"]:
        raise AssertionError(f"verify failed: {report['mismatches']}")
    return f"papers={report['sqlite']['papers']} graph={report['graph']['papers']} qdrant={report['qdrant']['points']}"


def check_metrics(settings: Settings) -> str:
    from lit_agent.eval.metrics import compute_run_metrics, persist_run_metrics

    metrics = compute_run_metrics(settings, "verify-run-1")
    if metrics["claims"] and metrics["grounding_rate"] is None:
        raise AssertionError("有 claims 时 grounding_rate 不应为 None")
    persist_run_metrics(settings, "verify-run-1")
    first = _scalars(settings, "SELECT COUNT(*) FROM metrics WHERE scope='run'")[0]
    persist_run_metrics(settings, "verify-run-1")
    second = _scalars(settings, "SELECT COUNT(*) FROM metrics WHERE scope='run'")[0]
    if first != second:
        raise AssertionError(f"metrics not idempotent: {first} -> {second}")
    return f"claims={metrics['claims']} rows={second}"


def check_api(settings: Settings) -> str:
    from fastapi.testclient import TestClient

    from lit_agent.api.app import create_app

    client = TestClient(create_app(settings))
    health = client.get("/api/health")
    if health.status_code != 200 or not health.json()["ok"]:
        raise AssertionError(f"health: {health.status_code}")
    if client.get("/api/runs/does-not-exist").status_code != 404:
        raise AssertionError("未知 run 应为 404")
    # 3.3 起 Chat 已实装：不再要求 501（P3 的契约变化）
    if client.get("/api/topics/ai-agents/chat").status_code == 501:
        raise AssertionError("chat 已实装，不应再返回 501")
    with client.stream("GET", "/api/runs/verify-run-1/stream") as response:
        body = "".join(response.iter_text())
    if "event: end" not in body:
        raise AssertionError("SSE 未以 end 结束")
    paths = len(client.get("/openapi.json").json()["paths"])
    if paths < 16:
        raise AssertionError(f"openapi paths: {paths}")
    return f"health/404/chat/sse ok; openapi paths={paths}"


def check_doctor(settings: Settings) -> str:
    from lit_agent.doctor import run_doctor

    results, ok = run_doctor()
    if not ok:
        failed = [item.name for item in results if not item.ok]
        raise AssertionError(f"doctor failed: {failed}")
    return f"{len(results)}/{len(results)} checks ok"


# --------------------------------------------------------------------------- #
# 在线断言
# --------------------------------------------------------------------------- #
def check_online_e2e(settings: Settings) -> str:
    result = run_topic(settings, "ai-agents", run_id="verify-online")
    if result["state"] != "succeeded":
        raise AssertionError(f"online run failed: {result.get('failure_report')}")
    papers = _paper_count(settings)
    if papers == 0:
        raise AssertionError("在线抓取后 papers 仍为 0")
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            row = conn.execute(
                text("SELECT claims_json, degraded FROM reports WHERE run_id='verify-online'")
            ).one()
    finally:
        engine.dispose()
    claims = json.loads(row[0])
    cited = sum(1 for claim in claims if claim.get("citations"))
    if not claims or cited != len(claims):
        raise AssertionError(f"claims={len(claims)} cited={cited}")
    if row[1] in (1, True):
        raise AssertionError("有真实证据时不应 degraded")
    return f"papers={papers} claims={len(claims)} cited={cited}"


def check_online_stores(settings: Settings) -> str:
    # 新增了 100 篇真实论文 → 先重建派生库，再对账（D6 的定义是"可重建 + 对账一致"）
    rebuild_graph(settings)
    rebuild_vector(settings, embedder=HashingEmbedder())
    report = verify_counts(settings, embedder=HashingEmbedder())
    if not report["ok"]:
        raise AssertionError(f"reconcile failed: {report['mismatches']}")
    # F2/G-01 回归门：真实数据必须有作者（此前恒为 0）
    authors = report["sqlite"]["authors"]
    links = report["sqlite"]["authorships"]
    if report["sqlite"]["papers"] > 0 and authors == 0:
        raise AssertionError("papers>0 但 authors=0（G-01 回归）")
    if authors and links < authors:
        raise AssertionError(f"authorships({links}) < authors({authors})")
    return (
        f"{report['sqlite']['papers']}/{report['graph']['papers']}/{report['qdrant']['points']}"
        f" authors={authors} links={links}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 1.1 exit verification")
    parser.add_argument("--online", action="store_true", help="额外跑真实 arXiv 端到端")
    parser.add_argument("--offline", action="store_true", help="只跑离线断言（默认行为，显式写出）")
    parser.add_argument("--root", default=DEFAULT_ROOT, help="临时数据目录")
    parser.add_argument("--json", default=None, help="红绿表输出路径")
    parser.add_argument("--keep", action="store_true", help="保留临时目录")
    args = parser.parse_args(argv)

    root = Path(args.root)
    shutil.rmtree(root, ignore_errors=True)
    settings = _settings(root)
    report = Report()

    def run(name: str, fn: Callable[[Settings], str]) -> None:
        started = time.time()
        try:
            detail = fn(settings)
            report.add(name, True, detail, time.time() - started)
        except Exception as exc:  # noqa: BLE001 - 验证器必须记录而不是崩溃
            report.add(
                name, False, f"{type(exc).__name__}: {str(exc)[:160]}", time.time() - started
            )

    try:
        upgrade_database(settings)
        _seed(settings)
        run("structure", check_structure)
        run("schema", check_schema)
        run("doctor", check_doctor)
        run("events", check_events)
        run("guards+budget", check_guards)
        run("runner(offline)", check_runner_offline)
        run("idempotency", check_idempotent)
        run("locks", check_lock)
        run("stores", check_stores)
        run("metrics", check_metrics)
        run("api+sse", check_api)

        if args.online:
            _seed(settings, papers=0, source="arxiv")
            run("e2e(online/arxiv)", check_online_e2e)
            run("stores(online)", check_online_stores)

        report.emit(Path(args.json) if args.json else None)
        return 0 if report.ok else 1
    finally:
        if not args.keep:
            shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())

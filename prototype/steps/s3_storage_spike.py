"""S3 存储栈可行性（Phase 0 Spike 3）。

要回答的问题
    1) 三库写入是否可行且**幂等**（重复导入计数零增长）？
    2) 万级规模下导入耗时、四类查询 P50/P95、磁盘占用是多少？
    3) 是否需要换库（Kuzu→Neo4j / Qdrant→Milvus）？
    4) 常见问题与边界情况的应对：关系 MERGE 语义、单写者/并发、local 模式多客户端、
       冷启动 vs 热查询、索引可重建（F2）、异常数据（未来日期/超短标题）、非 ASCII 标题。

产出
    out/s3_storage.json   指标 + 各探针结论 + 失败计数
    out/s3_run.log        完整运行日志
    out/events.jsonl、logs/app.jsonl（run_id 关联）

用法
    uv run python steps/s3_storage_spike.py --papers 5000
    uv run python steps/s3_storage_spike.py --papers 500 --no-rebuild-check   # 快速冒烟
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import sqlite3
import sys
import time
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lit_agent_min import (  # noqa: E402
    EventType,
    Severity,
    bind_context,
    clear_context,
    load_settings,
    log_event,
    open_event_log,
    setup_logging,
)

VECTOR_DIM = 1024
TOPIC_NAMES = {"T1": "multi-agent LLM orchestration reliability", "T2": "edge VLM deployment"}


# --------------------------------------------------------------------------- #
# 数据准备：真实元数据（S1/S1b 产出）+ 合成补足
# --------------------------------------------------------------------------- #
def load_real_records(out_dir: Path) -> list[dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for name in ("s1b_records.csv", "s1_coverage.csv"):
        path = out_dir / name
        if not path.exists():
            continue
        for row in csv.DictReader(path.open(encoding="utf-8")):
            paper_id = (row.get("paper_id") or "").strip()
            if not paper_id or paper_id in records:
                continue
            records[paper_id] = {
                "paper_id": paper_id,
                "title": (row.get("title") or "").strip(),
                "year": int(row["year"]) if str(row.get("year", "")).isdigit() else None,
                "venue": (row.get("venue") or "").strip(),
                "doi": (row.get("doi") or "").strip(),
                "source": (row.get("source") or "openalex").strip(),
                "topic": (row.get("topic") or "T1").strip(),
                "synthetic": False,
            }
    return list(records.values())


def build_dataset(
    real: list[dict[str, Any]], target: int, seed: int = 20261007
) -> list[dict[str, Any]]:
    """真实记录去重后不足 target 时，用确定性扰动补齐（标记 synthetic=True）。"""
    dataset = [dict(row) for row in real[:target]]
    index = 0
    while len(dataset) < target:
        base = real[index % len(real)] if real else None
        index += 1
        if base is None:
            break
        dataset.append(
            {
                "paper_id": f"{base['paper_id']}-syn{index}",
                "title": f"{base['title']} (synthetic variant {index})",
                "year": (base["year"] or 2024) - (index % 4),
                "venue": base["venue"],
                "doi": "",
                "source": base["source"],
                "topic": "T1" if index % 2 else "T2",
                "synthetic": True,
            }
        )
    # 注入 2 条故意异常记录，用于验证"入库前合理性校验"探针能检出
    if len(dataset) >= 2:
        dataset[-2].update(
            {
                "paper_id": "probe-bad-future",
                "title": "Future dated record",
                "year": 2051,
                "synthetic": True,
            }
        )
        dataset[-1].update(
            {"paper_id": "probe-bad-short", "title": "Moral", "year": 2024, "synthetic": True}
        )
    return dataset[:target]


def synth_authors(paper_id: str, n: int = 2) -> list[dict[str, str]]:
    seed = abs(hash(paper_id)) % 997
    return [
        {
            "author_id": f"A{(seed + i * 13) % 1500}",
            "name": f"Author {(seed + i * 13) % 1500}",
            "name_norm": f"author {(seed + i * 13) % 1500}",
        }
        for i in range(n)
    ]


def synth_citations(index: int, total: int, n: int = 2) -> list[int]:
    return [(index * 7 + k * 3 + 1) % total for k in range(n)]


def pseudo_vector(paper_id: str) -> list[float]:
    """确定性伪向量（真实 embedding 在 S5/P3 用 bge-m3；此处只验证存储与检索链路）。"""
    seed = abs(hash(paper_id)) % 10_000
    rng = random.Random(seed)
    return [rng.random() for _ in range(VECTOR_DIM)]


# --------------------------------------------------------------------------- #
# 三库写入
# --------------------------------------------------------------------------- #
def init_sqlite(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS papers(
            paper_id TEXT PRIMARY KEY, title TEXT, year INTEGER, venue TEXT, doi TEXT,
            source TEXT, topic TEXT, is_oa INTEGER, synthetic INTEGER, discovered_at TEXT);
        CREATE TABLE IF NOT EXISTS authors(
            paper_id TEXT, author_id TEXT, name_norm TEXT, PRIMARY KEY(paper_id, author_id));
        CREATE TABLE IF NOT EXISTS citations(src_id TEXT, dst_id TEXT, PRIMARY KEY(src_id, dst_id));
        """
    )
    conn.commit()
    return conn


def sqlite_upsert(
    conn: sqlite3.Connection,
    rows: list[dict[str, Any]],
    authors: dict[str, list[dict[str, str]]],
    cites: dict[str, list[str]],
) -> None:
    now = datetime.now(UTC).isoformat()
    conn.executemany(
        "INSERT OR REPLACE INTO papers VALUES(?,?,?,?,?,?,?,?,?,?)",
        [
            (
                row["paper_id"],
                row["title"],
                row["year"],
                row["venue"],
                row["doi"],
                row["source"],
                row["topic"],
                1,
                int(row["synthetic"]),
                now,
            )
            for row in rows
        ],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO authors VALUES(?,?,?)",
        [(pid, a["author_id"], a["name_norm"]) for pid, alist in authors.items() for a in alist],
    )
    conn.executemany(
        "INSERT OR REPLACE INTO citations VALUES(?,?)",
        [(src, dst) for src, dsts in cites.items() for dst in dsts],
    )
    conn.commit()


def reset_store_path(path: Path) -> str:
    """清空一个存储路径——**文件或目录都支持**，并清掉可能的同级锁/WAL 文件。

    实测教训（S3 第一轮）：Kuzu 的数据库路径是一个**单文件**（不在一个目录里）。
    早期实现写的是 `shutil.rmtree(path, ignore_errors=True)`：
      - 对文件抛 `NotADirectoryError`，而 `ignore_errors=True` 把它**静默吞掉**；
      - 结果旧库从未被删，`MERGE` 跨运行累积节点（两次运行论文数恰好都是 500 篇，掩盖了污染）；
      - 表现为 `expected_authors=631 / actual=957`，且 `extra - expected` 非空、`expected - extra` 为空
        （典型的"只多不少"跨运行残留特征）。
    """
    removed: list[str] = []
    for candidate in [
        path,
        *(path.with_name(f"{path.name}{sfx}") for sfx in (".wal", ".lock", ".shm")),
    ]:
        if candidate.is_dir():
            shutil.rmtree(candidate, ignore_errors=True)
            removed.append(f"{candidate.name}(dir)")
        elif candidate.exists():
            candidate.unlink()
            removed.append(f"{candidate.name}(file)")
    return ",".join(removed) if removed else "absent"


def store_is_empty(conn: Any, labels: Iterable[str]) -> dict[str, int]:
    """导入前确认库是**空的**——这是"旧库残留"这类静默 bug 的唯一可靠哨兵。"""
    return {label: kuzu_scalar(conn, f"MATCH (n:{label}) RETURN count(n)") for label in labels}


def path_size_mb(path: Path) -> float:
    """统计存储占用：文件按自身大小，目录递归求和（Kuzu=文件，Qdrant=目录）。"""
    if not path.exists():
        return 0.0
    if path.is_file():
        return round(path.stat().st_size / 1_048_576, 2)
    total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    return round(total / 1_048_576, 2)


def init_kuzu(path: Path) -> tuple[Any, Any, list[str]]:
    import kuzu

    # 三个实测约束：
    # 1) Kuzu 的数据库路径是**文件**（不是目录）；传一个已存在的目录 → "Database path cannot be a directory"；
    # 2) 传一个已存在的**旧库文件**不会报错——它会直接打开旧库，所以必须显式 reset（见 reset_store_path）；
    # 3) Windows 上 Kuzu 无法打开含非 ASCII 的路径 → 配置里 kuzu_path 指向 ASCII 目录。
    path.parent.mkdir(parents=True, exist_ok=True)
    notes: list[str] = []
    removed = reset_store_path(path)
    if removed != "absent":
        notes.append(f"导入前清理了已存在的存储路径：{removed}")
    db = kuzu.Database(str(path))
    conn = kuzu.Connection(db)
    ddl = [
        "CREATE NODE TABLE IF NOT EXISTS Paper(paper_id STRING PRIMARY KEY, title STRING, year INT64, source STRING, discovered_at TIMESTAMP)",
        "CREATE NODE TABLE IF NOT EXISTS Author(author_id STRING PRIMARY KEY, name STRING, name_norm STRING)",
        "CREATE REL TABLE IF NOT EXISTS PAPER_AUTHOR(FROM Paper TO Author, year INT64)",
        "CREATE REL TABLE IF NOT EXISTS CITES(FROM Paper TO Paper, first_seen TIMESTAMP)",
    ]
    for statement in ddl:
        try:
            conn.execute(statement)
        except Exception as exc:  # noqa: BLE001 - 记录而非崩溃
            notes.append(f"DDL 失败（可能已存在）：{statement[:60]}… -> {str(exc)[:120]}")
    return db, conn, notes


def kuzu_scalar(conn: Any, cypher: str, params: dict[str, Any] | None = None) -> Any:
    result = conn.execute(cypher, params) if params else conn.execute(cypher)
    try:
        row = result.get_next() if result.has_next() else None
    except Exception:  # noqa: BLE001 - 兼容不同版本的 QueryResult
        row = next(iter(result), None)
    if row is None:
        return None
    return row[0] if isinstance(row, (list, tuple)) else row


def kuzu_import(
    conn: Any,
    rows: list[dict[str, Any]],
    authors: dict[str, list[dict[str, str]]],
    cites: dict[str, list[str]],
) -> dict[str, Any]:
    """写入节点与边；关系用 MERGE，若引擎不支持则记录并回退到"先查后建"。"""
    now = datetime.now(UTC)  # 注意：Kuzu 类型严格，TIMESTAMP 参数必须传 datetime，不能传 ISO 字符串
    failures: list[str] = []
    edge_strategies: dict[str, int] = {"merge": 0, "create_after_check": 0, "preexisting": 0}
    for row in rows:
        try:
            conn.execute(
                "MERGE (p:Paper {paper_id: $pid}) ON CREATE SET p.title=$title, p.year=$year, p.source=$source, p.discovered_at=$ts",
                {
                    "pid": row["paper_id"],
                    "title": row["title"][:200],
                    "year": row["year"],
                    "source": row["source"],
                    "ts": now,
                },
            )
        except Exception as exc:  # noqa: BLE001
            failures.append(f"paper:{row['paper_id']}:{str(exc)[:80]}")
    for pid, alist in authors.items():
        for author in alist:
            try:
                conn.execute(
                    "MERGE (a:Author {author_id: $aid}) ON CREATE SET a.name=$name, a.name_norm=$norm",
                    {
                        "aid": author["author_id"],
                        "name": author["name"],
                        "norm": author["name_norm"],
                    },
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(f"author:{author['author_id']}:{str(exc)[:80]}")
                continue
            edge_strategies[
                _add_edge(
                    conn,
                    "PAPER_AUTHOR",
                    "Paper",
                    "paper_id",
                    pid,
                    "Author",
                    "author_id",
                    author["author_id"],
                )
            ] += 1
    for src, dsts in cites.items():
        for dst in dsts:
            edge_strategies[
                _add_edge(conn, "CITES", "Paper", "paper_id", src, "Paper", "paper_id", dst)
            ] += 1
    return {
        "edge_strategies": edge_strategies,
        "failures": failures[:5],
        "failure_count": len(failures),
    }


def _add_edge(
    conn: Any,
    rel: str,
    src_label: str,
    src_key: str,
    src_id: str,
    dst_label: str,
    dst_key: str,
    dst_id: str,
) -> str:
    """写一条边：优先 MATCH+MERGE；若引擎不支持则"先查后建"（保持幂等）。

    注意：当任一端点不存在时，MATCH 返回空集，MERGE 会**静默不写**（不报错）——
    所以调用方必须用写入后的计数校验来发现"边丢失"。
    """
    params = {"src": src_id, "dst": dst_id}
    match_clause = f"MATCH (a:{src_label} {{{src_key}:$src}}), (b:{dst_label} {{{dst_key}:$dst}})"
    try:
        conn.execute(f"{match_clause} MERGE (a)-[:{rel}]->(b)", params)
        return "merge"
    except Exception:  # noqa: BLE001 - 回退到"先查后建"
        exists = kuzu_scalar(
            conn,
            f"{match_clause} MATCH (a)-[r:{rel}]->(b) RETURN count(r)",
            params,
        )
        if exists:
            return "preexisting"
        conn.execute(f"{match_clause} CREATE (a)-[:{rel}]->(b)", params)
        return "create_after_check"


def init_qdrant(path: Path, collection: str = "papers") -> tuple[Any, list[str]]:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams

    path.mkdir(parents=True, exist_ok=True)
    client = QdrantClient(path=str(path))
    notes: list[str] = []
    try:
        try:
            exists = client.collection_exists(collection)
        except AttributeError:  # 兼容旧版客户端
            exists = collection in [c.name for c in client.get_collections().collections]
        if not exists:
            client.create_collection(
                collection, vectors_config=VectorParams(size=VECTOR_DIM, distance=Distance.COSINE)
            )
    except Exception as exc:  # noqa: BLE001
        notes.append(f"创建 collection 失败：{str(exc)[:120]}")
    return client, notes


def qdrant_upsert(
    client: Any, rows: list[dict[str, Any]], collection: str = "papers", batch: int = 500
) -> dict[str, Any]:
    from qdrant_client.models import PointStruct

    failures = 0
    for start in range(0, len(rows), batch):
        chunk = rows[start : start + batch]
        points = [
            PointStruct(
                id=abs(hash(row["paper_id"])) % (2**53),
                vector=pseudo_vector(row["paper_id"]),
                payload={
                    "paper_id": row["paper_id"],
                    "title": row["title"][:200],
                    "year": row["year"],
                    "source": row["source"],
                    "topic_ids": [row["topic"]],
                },
            )
            for row in chunk
        ]
        try:
            client.upsert(collection, points=points)
        except Exception as exc:  # noqa: BLE001
            failures += len(points)
            log_event(
                Severity.ERROR,
                "qdrant_upsert_failed",
                "Qdrant 批量写入失败",
                error_code="E_DATA_QDRANT_WRITE",
                batch_start=start,
                error=str(exc)[:160],
            )
    return {"failures": failures}


# --------------------------------------------------------------------------- #
# 查询与测量
# --------------------------------------------------------------------------- #
def timed(fn: Callable[[], Any], rounds: int) -> dict[str, Any]:
    latencies: list[float] = []
    errors = 0
    for _ in range(rounds):
        started = time.perf_counter()
        try:
            fn()
        except Exception:  # noqa: BLE001
            errors += 1
        latencies.append((time.perf_counter() - started) * 1000)
    latencies.sort()
    return {
        "rounds": rounds,
        "errors": errors,
        "p50_ms": round(median(latencies), 2),
        "p95_ms": round(latencies[int(len(latencies) * 0.95) - 1], 2),
        "max_ms": round(max(latencies), 2),
    }


def dir_size_mb(path: Path) -> float:
    """已由 path_size_mb 取代（Kuzu 路径是文件，rglob 会漏算）；保留薄封装避免旧调用失效。"""
    return path_size_mb(path)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Spike S3：存储栈可行性")
    parser.add_argument("--papers", type=int, default=5000)
    parser.add_argument("--rounds", type=int, default=30, help="每类查询重复次数")
    parser.add_argument("--rebuild-check", action="store_true", default=True)
    parser.add_argument("--no-rebuild-check", dest="rebuild_check", action="store_false")
    parser.add_argument("--summary", default="out/s3_storage.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    setup_logging(settings)
    run_id = f"p0-s3-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    log = open_event_log(settings.paths.out_dir / "events.jsonl", run_id=run_id)
    clear_context()
    bind_context(run_id=run_id, stage="S3_storage", agent="single")

    out_dir = settings.paths.out_dir
    data_dir = settings.paths.data_dir
    real = load_real_records(out_dir)
    dataset = build_dataset(real, args.papers)
    authors = {row["paper_id"]: synth_authors(row["paper_id"]) for row in dataset}
    cites = {
        row["paper_id"]: [dataset[j]["paper_id"] for j in synth_citations(i, len(dataset))]
        for i, row in enumerate(dataset)
    }

    log_event(
        Severity.INFO,
        "spike_started",
        "S3 存储栈验证开始",
        papers=len(dataset),
        real_used=min(len(real), len(dataset)),
        synthetic=max(0, len(dataset) - len(real)),
        vector_dim=VECTOR_DIM,
    )
    log.emit(EventType.PHASE_CHANGE, payload={"spike": "S3", "papers": len(dataset)})

    probes: dict[str, Any] = {}

    # ---- SQLite（真相源） ----
    started = time.perf_counter()
    sqlite_path = data_dir / "sqlite.db"
    if sqlite_path.exists():
        sqlite_path.unlink()
    sqlite_conn = init_sqlite(sqlite_path)
    sqlite_upsert(sqlite_conn, dataset, authors, cites)
    sqlite_seconds = time.perf_counter() - started

    # ---- Kuzu（图） ----
    started = time.perf_counter()
    kuzu_path = settings.paths.kuzu_path
    kuzu_db, kuzu_conn, kuzu_ddl_notes = init_kuzu(kuzu_path)
    # 空库哨兵：必须在导入前确认，否则"旧库残留"会被 MERGE 悄悄掩盖成计数不一致
    kuzu_pre_import = store_is_empty(kuzu_conn, ("Paper", "Author"))
    kuzu_result = kuzu_import(kuzu_conn, dataset, authors, cites)
    kuzu_seconds = time.perf_counter() - started
    kuzu_counts = {
        "papers": kuzu_scalar(kuzu_conn, "MATCH (p:Paper) RETURN count(p)"),
        "authors": kuzu_scalar(kuzu_conn, "MATCH (a:Author) RETURN count(a)"),
        "paper_author_edges": kuzu_scalar(
            kuzu_conn, "MATCH ()-[r:PAPER_AUTHOR]->() RETURN count(r)"
        ),
        "cites_edges": kuzu_scalar(kuzu_conn, "MATCH ()-[r:CITES]->() RETURN count(r)"),
    }

    # ---- Qdrant（向量） ----
    started = time.perf_counter()
    reset_store_path(settings.paths.qdrant_path)
    qdrant_client, qdrant_notes = init_qdrant(settings.paths.qdrant_path)
    qdrant_result = qdrant_upsert(qdrant_client, dataset)
    qdrant_seconds = time.perf_counter() - started
    qdrant_count = qdrant_client.count("papers").count

    # ---- 写入后计数校验（发现"边静默丢失"） ----
    expected = {
        "papers": len(dataset),
        "authors": len({a["author_id"] for alist in authors.values() for a in alist}),
        "paper_author_edges": sum(len(alist) for alist in authors.values()),
        "cites_edges": sum(len(dsts) for dsts in cites.values()),
        "qdrant_points": len(dataset),
    }
    write_verification = {
        "expected": expected,
        "actual": {
            "papers": kuzu_counts["papers"],
            "authors": kuzu_counts["authors"],
            "paper_author_edges": kuzu_counts["paper_author_edges"],
            "cites_edges": kuzu_counts["cites_edges"],
            "qdrant_points": qdrant_count,
        },
    }
    write_verification["mismatches"] = {
        key: {"expected": value, "actual": write_verification["actual"].get(key)}
        for key, value in expected.items()
        if value != write_verification["actual"].get(key)
    }
    if write_verification["mismatches"]:
        log_event(
            Severity.ERROR,
            "write_verification_failed",
            "写入计数与预期不一致（可能边静默丢失）",
            error_code="E_DATA_COUNT_MISMATCH",
            mismatches=write_verification["mismatches"],
        )

    # 空库哨兵：非空说明 reset 没生效（Kuzu 路径是文件，用 rmtree 清理会静默失败）
    store_not_empty = {k: v for k, v in kuzu_pre_import.items() if v}
    if store_not_empty:
        log_event(
            Severity.ERROR,
            "store_not_empty_before_import",
            "导入前图库非空：reset 未生效，计数校验将不可信",
            error_code="E_STORE_NOT_EMPTY",
            detail=store_not_empty,
            reset_removed=kuzu_ddl_notes,
        )

    log_event(
        Severity.INFO,
        "import_finished",
        "三库导入完成",
        sqlite_s=round(sqlite_seconds, 2),
        kuzu_s=round(kuzu_seconds, 2),
        qdrant_s=round(qdrant_seconds, 2),
        kuzu_counts=kuzu_counts,
        qdrant_count=qdrant_count,
        mismatches=len(write_verification["mismatches"]),
    )

    # ---- 四类查询 ----
    from qdrant_client.models import FieldCondition, Filter, MatchValue, Range

    sample_id = dataset[0]["paper_id"]
    sample_author = authors[sample_id][0]["author_id"]
    queries = {
        "vector_top10_filtered": timed(
            lambda: qdrant_client.query_points(
                "papers",
                query=pseudo_vector(sample_id),
                query_filter=Filter(
                    must=[
                        FieldCondition(key="topic_ids", match=MatchValue(value="T1")),
                        FieldCondition(key="year", range=Range(gte=2020)),
                    ]
                ),
                limit=10,
            ),
            args.rounds,
        ),
        "graph_2hop_author_paper_cites": timed(
            lambda: kuzu_scalar(
                kuzu_conn,
                "MATCH (a:Author {author_id:$aid})<-[:PAPER_AUTHOR]-(p:Paper)-[:CITES]->(q:Paper) RETURN count(q)",
                {"aid": sample_author},
            ),
            args.rounds,
        ),
        "author_recent_years_agg": timed(
            lambda: kuzu_scalar(
                kuzu_conn,
                "MATCH (a:Author {author_id:$aid})<-[:PAPER_AUTHOR]-(p:Paper) WHERE p.year >= 2020 RETURN p.year, count(p)",
                {"aid": sample_author},
            ),
            args.rounds,
        ),
        "sqlite_lookup_by_id": timed(
            lambda: sqlite_conn.execute(
                "SELECT title, year, venue FROM papers WHERE paper_id=?", (sample_id,)
            ).fetchone(),
            args.rounds,
        ),
    }
    first_vector_query_ms = queries["vector_top10_filtered"]["max_ms"]

    # ---- 探针 1：幂等（重复导入） ----
    started = time.perf_counter()
    sqlite_upsert(sqlite_conn, dataset, authors, cites)
    kuzu_reimport = kuzu_import(kuzu_conn, dataset, authors, cites)
    qdrant_reimport = qdrant_upsert(qdrant_client, dataset)
    idempotent = {
        "seconds": round(time.perf_counter() - started, 2),
        "sqlite_papers": sqlite_conn.execute("SELECT count(*) FROM papers").fetchone()[0],
        "kuzu_papers": kuzu_scalar(kuzu_conn, "MATCH (p:Paper) RETURN count(p)"),
        "kuzu_cites": kuzu_scalar(kuzu_conn, "MATCH ()-[r:CITES]->() RETURN count(r)"),
        "qdrant_points": qdrant_client.count("papers").count,
        "kuzu_reimport_failures": kuzu_reimport["failure_count"],
        "qdrant_reimport_failures": qdrant_reimport["failures"],
    }
    probes["idempotency"] = idempotent

    # ---- 探针 2：Qdrant local 模式多客户端（并发访问限制） ----
    second = None
    try:
        from qdrant_client import QdrantClient as _QC

        second = _QC(path=str(settings.paths.qdrant_path))
        second.count("papers")
        probes["qdrant_second_client"] = {"allowed": True}
    except Exception as exc:  # noqa: BLE001
        probes["qdrant_second_client"] = {"allowed": False, "error": str(exc)[:160]}
    finally:
        if second is not None:
            second.close()

    # ---- 探针 3：Kuzu 第二连接写（单写者语义） ----
    db2 = conn2 = None
    try:
        db_path = str(settings.paths.kuzu_path)
        import kuzu

        db2 = kuzu.Database(db_path)
        conn2 = kuzu.Connection(db2)
        conn2.execute("MERGE (p:Paper {paper_id: $pid})", {"pid": "probe-conn2"})
        probes["kuzu_second_connection_write"] = {
            "allowed": True,
            "extra_node_created": kuzu_scalar(
                conn2, "MATCH (p:Paper {paper_id:'probe-conn2'}) RETURN count(p)"
            ),
        }
        conn2.execute("MATCH (p:Paper {paper_id:'probe-conn2'}) DELETE p")
    except Exception as exc:  # noqa: BLE001
        probes["kuzu_second_connection_write"] = {"allowed": False, "error": str(exc)[:160]}
    finally:
        if conn2 is not None:
            conn2.close()
        if db2 is not None:
            db2.close()

    # ---- 探针 4：非法向量维度（写入失败的可见性） ----
    try:
        from qdrant_client.models import PointStruct

        qdrant_client.upsert(
            "papers", points=[PointStruct(id=1, vector=[0.1, 0.2], payload={"paper_id": "bad"})]
        )
        probes["bad_vector_dimension"] = {"rejected": False}
    except Exception as exc:  # noqa: BLE001
        probes["bad_vector_dimension"] = {"rejected": True, "error": str(exc)[:140]}

    # ---- 探针 5：非 ASCII / 超长标题 ----
    try:
        kuzu_conn.execute(
            "MERGE (p:Paper {paper_id: $pid}) ON CREATE SET p.title=$title, p.year=$year, p.source=$source",
            {
                "pid": "probe-unicode",
                "title": "中文标题：面向边缘设备的量化视觉语言模型部署与评估" * 3,
                "year": 2025,
                "source": "probe",
            },
        )
        probes["unicode_title"] = {
            "written": True,
            "readback_len": len(
                kuzu_scalar(kuzu_conn, "MATCH (p:Paper {paper_id:'probe-unicode'}) RETURN p.title")
                or ""
            ),
        }
        kuzu_conn.execute("MATCH (p:Paper {paper_id:'probe-unicode'}) DELETE p")
    except Exception as exc:  # noqa: BLE001
        probes["unicode_title"] = {"written": False, "error": str(exc)[:140]}

    # ---- 探针 6：异常数据检出（未来日期 / 超短标题） ----
    future = [
        row["paper_id"]
        for row in dataset
        if row["year"] and row["year"] > datetime.now(UTC).year + 1
    ]
    short_titles = [row["paper_id"] for row in dataset if len(row["title"].strip()) <= 10]
    probes["bad_records_detected"] = {
        "future_year": len(future),
        "short_title": len(short_titles),
        "examples": (future[:2] + short_titles[:2]),
    }

    # ---- 探针 7：索引可重建（F2：删 Kuzu/Qdrant，从 SQLite 重建） ----
    if args.rebuild_check:
        before = {"kuzu": kuzu_counts, "qdrant": qdrant_count}
        kuzu_conn.close()
        qdrant_client.close()
        reset_store_path(settings.paths.kuzu_path)
        reset_store_path(settings.paths.qdrant_path)
        started = time.perf_counter()
        kuzu_db2, kuzu_conn2, _ = init_kuzu(settings.paths.kuzu_path)
        kuzu_rebuild_pre = store_is_empty(kuzu_conn2, ("Paper", "Author"))
        kuzu_import(kuzu_conn2, dataset, authors, cites)
        client2, _ = init_qdrant(settings.paths.qdrant_path)
        qdrant_upsert(client2, dataset)
        after = {
            "kuzu": {
                "papers": kuzu_scalar(kuzu_conn2, "MATCH (p:Paper) RETURN count(p)"),
                "cites_edges": kuzu_scalar(kuzu_conn2, "MATCH ()-[r:CITES]->() RETURN count(r)"),
            },
            "qdrant": client2.count("papers").count,
        }
        probes["index_rebuild"] = {
            "seconds": round(time.perf_counter() - started, 2),
            "pre_rebuild_empty": kuzu_rebuild_pre,
            "before": before,
            "after": after,
            "counts_match": (
                before["kuzu"]["papers"] == after["kuzu"]["papers"]
                and before["kuzu"]["cites_edges"] == after["kuzu"]["cites_edges"]
                and before["qdrant"] == after["qdrant"]
            ),
        }
        client2.close()
        kuzu_conn2.close()
        kuzu_db2.close()

    # 量磁盘前必须关闭存储句柄：Kuzu **只在 `Database.close()` 时 checkpoint 落盘**
    # （`Connection.close()` 不触发）。实测：导入 300 篇后文件 0.004MB，conn.close() 仍 0.004MB，
    # db.close() 后 2.426MB —— 关早了会读到假小值 0.0MB。
    kuzu_conn.close()
    kuzu_db.close()
    qdrant_client.close()
    disk = {
        "sqlite_mb": round(sqlite_path.stat().st_size / 1_048_576, 2)
        if sqlite_path.exists()
        else 0,
        "kuzu_mb": path_size_mb(settings.paths.kuzu_path),
        "qdrant_mb": path_size_mb(settings.paths.qdrant_path),
    }
    disk["total_mb"] = round(sum(disk.values()), 2)
    disk["note"] = "Kuzu=单文件（close 后 checkpoint 落盘），Qdrant=目录递归求和，SQLite=单文件"

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "papers": len(dataset),
        "real_records": min(len(real), len(dataset)),
        "synthetic_records": max(0, len(dataset) - len(real)),
        "vector_dim": VECTOR_DIM,
        "import_seconds": {
            "sqlite": round(sqlite_seconds, 2),
            "kuzu": round(kuzu_seconds, 2),
            "qdrant": round(qdrant_seconds, 2),
        },
        "counts": {"sqlite_papers": len(dataset), "kuzu": kuzu_counts, "qdrant": qdrant_count},
        "import_problems": {
            "kuzu_ddl_notes": kuzu_ddl_notes,
            "kuzu_edge_strategies": kuzu_result["edge_strategies"],
            "kuzu_failure_count": kuzu_result["failure_count"],
            "kuzu_failure_examples": kuzu_result["failures"],
            "qdrant_notes": qdrant_notes,
        },
        "write_verification": write_verification,
        "pre_import_empty": kuzu_pre_import,
        "queries": queries,
        "probes": probes,
        "disk_mb": disk,
        "first_vector_query_ms": first_vector_query_ms,
    }
    summary_path = settings.paths.out_dir.parent / args.summary
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"run_id   {run_id}")
    print(
        f"papers   {len(dataset)}（real_used={min(len(real), len(dataset))}, "
        f"synthetic={max(0, len(dataset) - len(real))}）"
    )
    print(
        f"import   sqlite={sqlite_seconds:.2f}s kuzu={kuzu_seconds:.2f}s qdrant={qdrant_seconds:.2f}s"
    )
    print(f"counts   kuzu={kuzu_counts} qdrant={qdrant_count}")
    print(f"verify   mismatches={write_verification['mismatches']}")
    print(
        f"problems kuzu_edges={kuzu_result['edge_strategies']} "
        f"kuzu_failures={kuzu_result['failure_count']} qdrant_failures={qdrant_result['failures']}"
    )
    for name, stat in queries.items():
        print(
            f"query    {name}: p50={stat['p50_ms']}ms p95={stat['p95_ms']}ms errors={stat['errors']}"
        )
    print(f"idempotent {json.dumps(idempotent, ensure_ascii=False)}")
    print(f"probes   {json.dumps(probes, ensure_ascii=False)[:600]}")
    print(f"disk     {disk}")
    print(f"summary  {summary_path}")

    log_event(
        Severity.INFO, "spike_finished", "S3 完成", papers=len(dataset), disk_mb=disk["total_mb"]
    )
    clear_context()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""存储层（Phase 0 step 5.4 的最小实现；Phase 1 扩到三库并迁 SQLAlchemy）。

本轮范围（刻意的）
- **只做 SQLite 真相源**：papers / authors / citations / claims / sync_state / paper_merges。
- Kuzu（图）与 Qdrant（向量）本轮**不接**，原因：① S3 已验证两库可用且幂等；
  ② 本轮无本地 embedding（bge-m3 未就位），把词法向量塞进 Qdrant 只是"假向量"，不如不接；
  ③ S5 的验收是"闭环 + 证据可回查"，SQLite 足够作为真相源。接线动作留 Phase 1/P3。

继承 S3 的三条实测教训
- 写入后必须**计数对账**（`verify_counts`）：边端缺失时 Kuzu 的 `MATCH+MERGE` 会静默不写，
  同理 SQLite 的 `INSERT OR IGNORE` 也会让"应写数量"与"实写数量"不一致。
- 幂等靠**主键 + upsert**，不靠"先删后建"；重复运行计数必须零增长。
- 每次导入前检查**目标库是否为空**（`is_empty`），避免"旧库残留"被误判为本次结果。
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .models import Citation, Claim, Paper

__all__ = ["SqliteStore", "StoreCounts", "verify_counts"]

DDL = """
CREATE TABLE IF NOT EXISTS papers(
    paper_id     TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    abstract     TEXT,
    venue        TEXT,
    year         INTEGER,
    source       TEXT NOT NULL,
    oa_pdf_url   TEXT,
    first_seen   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS authors(
    paper_id   TEXT NOT NULL,
    author_id  TEXT NOT NULL,
    name       TEXT,
    name_norm  TEXT,
    position   INTEGER,
    PRIMARY KEY(paper_id, author_id)
);
CREATE TABLE IF NOT EXISTS citations(
    src_id TEXT NOT NULL,
    dst_id TEXT NOT NULL,
    PRIMARY KEY(src_id, dst_id)
);
CREATE TABLE IF NOT EXISTS claims(
    run_id     TEXT NOT NULL,
    claim_idx  INTEGER NOT NULL,
    text       TEXT NOT NULL,
    support    TEXT NOT NULL,
    citations  TEXT NOT NULL,
    PRIMARY KEY(run_id, claim_idx)
);
CREATE TABLE IF NOT EXISTS paper_merges(
    primary_id TEXT NOT NULL,
    merged_id  TEXT NOT NULL,
    run_id     TEXT,
    PRIMARY KEY(primary_id, merged_id)
);
CREATE TABLE IF NOT EXISTS sync_state(
    stream        TEXT PRIMARY KEY,
    cursor        TEXT,
    last_run_id   TEXT,
    last_run_at   TEXT,
    items_seen    INTEGER DEFAULT 0
);
"""


@dataclass
class StoreCounts:
    papers: int = 0
    authors: int = 0
    citations: int = 0
    claims: int = 0
    merges: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "papers": self.papers,
            "authors": self.authors,
            "citations": self.citations,
            "claims": self.claims,
            "merges": self.merges,
        }


def verify_counts(expected: dict[str, int], actual: dict[str, int]) -> dict[str, dict[str, int]]:
    """写入后计数对账；返回不一致项（空 dict = 全部一致）。"""
    mismatches: dict[str, dict[str, int]] = {}
    for key, want in expected.items():
        got = actual.get(key)
        if got != want:
            mismatches[key] = {"expected": want, "actual": got if got is not None else -1}
    return mismatches


class StoreSchemaError(RuntimeError):
    """既有库的表结构与当前契约不一致（例如 S3 spike 写入的旧 `papers` 表）。

    与 S3 的"旧库残留"同族：**不能假设目标库就是我们以为的那个库**。
    处理原则 = 显式检测 + 显式重置（`reset=True`），绝不静默改表或忽略缺失列。
    """


# 建表后必须存在的列（用于 schema 身份校验）
REQUIRED_COLUMNS: dict[str, set[str]] = {
    "papers": {
        "paper_id",
        "title",
        "abstract",
        "venue",
        "year",
        "source",
        "oa_pdf_url",
        "first_seen",
        "updated_at",
    },
    "authors": {"paper_id", "author_id", "name", "name_norm", "position"},
    "citations": {"src_id", "dst_id"},
    "claims": {"run_id", "claim_idx", "text", "support", "citations"},
    "paper_merges": {"primary_id", "merged_id", "run_id"},
    "sync_state": {"stream", "cursor", "last_run_id", "last_run_at", "items_seen"},
}

_DROP = "\n".join(f"DROP TABLE IF EXISTS {table};" for table in REQUIRED_COLUMNS)


class SqliteStore:
    """SQLite 真相源（幂等 upsert + 计数 + 增量游标 + schema 校验）。"""

    def __init__(self, path: str | Path, *, reset: bool = False) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        if reset:
            self.conn.executescript(_DROP)
            self.conn.commit()
        self.conn.executescript(DDL)
        self.conn.commit()
        self._check_schema()

    def _check_schema(self) -> None:
        """校验既有表确实具备契约列；不一致立即报错（提示用 `reset=True` 重建）。"""
        for table, required in REQUIRED_COLUMNS.items():
            existing = {
                row[1] for row in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
            missing = required - existing
            if missing:
                raise StoreSchemaError(
                    f"表 {table} 缺少列 {sorted(missing)}（库：{self.path}）。"
                    "可能是早期 spike 写入的旧结构；确认可丢弃后用 reset=True 重建。"
                )

    # -- 生命周期 ------------------------------------------------------------ #
    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> SqliteStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def is_empty(self) -> bool:
        return self.counts().papers == 0

    def counts(self) -> StoreCounts:
        def scalar(table: str) -> int:
            row = self.conn.execute(f"SELECT count(*) FROM {table}").fetchone()
            return int(row[0]) if row else 0

        return StoreCounts(
            papers=scalar("papers"),
            authors=scalar("authors"),
            citations=scalar("citations"),
            claims=scalar("claims"),
            merges=scalar("paper_merges"),
        )

    # -- 写入 ---------------------------------------------------------------- #
    def upsert_papers(self, papers: Iterable[Paper], *, run_id: str) -> dict[str, int]:
        """论文 + 作者 + 引用边；全部 upsert（幂等），返回"本次应写"的计数供对账。"""
        now = datetime.now(UTC).isoformat()
        papers = list(papers)
        paper_rows = [
            (
                p.paper_id,
                p.title,
                p.abstract or "",
                p.venue,
                p.year,
                p.source,
                p.oa_pdf_url,
                now,
                now,
            )
            for p in papers
        ]
        self.conn.executemany(
            """INSERT INTO papers(paper_id,title,abstract,venue,year,source,oa_pdf_url,
                                  first_seen,updated_at)
               VALUES(?,?,?,?,?,?,?,?,?)
               ON CONFLICT(paper_id) DO UPDATE SET
                 title=excluded.title, abstract=excluded.abstract, venue=excluded.venue,
                 year=excluded.year, source=excluded.source, oa_pdf_url=excluded.oa_pdf_url,
                 updated_at=excluded.updated_at""",
            paper_rows,
        )
        author_rows = [
            (p.paper_id, a.author_id, a.name, a.name_norm, pos)
            for p in papers
            for pos, a in enumerate(p.authors)
        ]
        self.conn.executemany(
            """INSERT INTO authors(paper_id,author_id,name,name_norm,position)
               VALUES(?,?,?,?,?)
               ON CONFLICT(paper_id,author_id) DO UPDATE SET
                 name=excluded.name, name_norm=excluded.name_norm, position=excluded.position""",
            author_rows,
        )
        known = {p.paper_id for p in papers}
        citation_rows = sorted(
            {(p.paper_id, ref) for p in papers for ref in p.references if ref and ref in known}
        )
        self.conn.executemany(
            "INSERT OR IGNORE INTO citations(src_id,dst_id) VALUES(?,?)", citation_rows
        )
        self.conn.commit()
        return {
            "papers": len(papers),
            "authors": len(author_rows),
            "citations": len(citation_rows),
        }

    def record_merges(self, merged: dict[str, list[str]], *, run_id: str) -> int:
        rows = [(primary, other, run_id) for primary, others in merged.items() for other in others]
        self.conn.executemany(
            "INSERT OR IGNORE INTO paper_merges(primary_id,merged_id,run_id) VALUES(?,?,?)", rows
        )
        self.conn.commit()
        return len(rows)

    def upsert_claims(self, run_id: str, claims: Iterable[Claim]) -> int:
        rows = []
        for idx, claim in enumerate(claims):
            citations = [
                {"paper_id": c.paper_id, "locator": c.locator, "snippet": c.snippet}
                for c in claim.citations
            ]
            import json

            rows.append(
                (
                    run_id,
                    idx,
                    claim.text,
                    str(claim.support),
                    json.dumps(citations, ensure_ascii=False),
                )
            )
        self.conn.executemany(
            """INSERT INTO claims(run_id,claim_idx,text,support,citations) VALUES(?,?,?,?,?)
               ON CONFLICT(run_id,claim_idx) DO UPDATE SET
                 text=excluded.text, support=excluded.support, citations=excluded.citations""",
            rows,
        )
        self.conn.commit()
        return len(rows)

    # -- 同步状态（5.1 增量游标） --------------------------------------------- #
    def get_cursor(self, stream: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT cursor,last_run_id,last_run_at,items_seen FROM sync_state WHERE stream=?",
            (stream,),
        ).fetchone()
        if not row:
            return None
        return {
            "cursor": row[0],
            "last_run_id": row[1],
            "last_run_at": row[2],
            "items_seen": row[3],
        }

    def set_cursor(self, stream: str, *, cursor: str | None, run_id: str, items_seen: int) -> None:
        self.conn.execute(
            """INSERT INTO sync_state(stream,cursor,last_run_id,last_run_at,items_seen)
               VALUES(?,?,?,?,?)
               ON CONFLICT(stream) DO UPDATE SET
                 cursor=excluded.cursor, last_run_id=excluded.last_run_id,
                 last_run_at=excluded.last_run_at, items_seen=excluded.items_seen""",
            (stream, cursor, run_id, datetime.now(UTC).isoformat(), items_seen),
        )
        self.conn.commit()

    # -- 读取 ---------------------------------------------------------------- #
    def paper_ids(self) -> set[str]:
        return {row[0] for row in self.conn.execute("SELECT paper_id FROM papers")}

    def citation_count_for(self, paper_id: str) -> int:
        row = self.conn.execute(
            "SELECT count(*) FROM citations WHERE dst_id=?", (paper_id,)
        ).fetchone()
        return int(row[0]) if row else 0

    @staticmethod
    def citation_keys(citations: Iterable[Citation]) -> list[str]:
        return [c.paper_id for c in citations]

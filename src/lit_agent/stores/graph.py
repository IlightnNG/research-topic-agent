"""Kuzu 图存储（guide §2.5）：**只存查询/展示必需字段**，全部 `MERGE` 幂等。

实测约束（kuzu 0.11.3）：
- 节点可用 `MERGE (p:Paper {paper_id:$id}) SET ...`（幂等 + 可更新）；
- 关系**不能**写进整条 pattern 的 MERGE（端节点会被当成新建 → 主键冲突），必须先
  `MATCH (a),(b)` 再 `MERGE (a)-[e:REL]->(b)`；
- 数据只在 `Database.close()` 时落盘（ADR-0003）→ 磁盘统计必须在 close 之后。
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import kuzu

from lit_agent.config import Settings
from lit_agent.errors import E_STORE_SCHEMA_MISMATCH, LitError
from lit_agent.selftest import assert_ascii_path

__all__ = ["NODE_DDL", "REL_DDL", "GraphStore", "paper_rows"]

NODE_DDL: tuple[str, ...] = (
    "CREATE NODE TABLE IF NOT EXISTS Paper(paper_id STRING PRIMARY KEY, title STRING,"
    " year INT64, source STRING, venue_id STRING, discovered_at STRING)",
    "CREATE NODE TABLE IF NOT EXISTS Author(author_id STRING PRIMARY KEY, name STRING,"
    " name_norm STRING)",
    "CREATE NODE TABLE IF NOT EXISTS Venue(venue_id STRING PRIMARY KEY, name STRING)",
    "CREATE NODE TABLE IF NOT EXISTS Topic(topic_id STRING PRIMARY KEY, name STRING)",
)

REL_DDL: tuple[str, ...] = (
    "CREATE REL TABLE IF NOT EXISTS PAPER_AUTHOR(FROM Paper TO Author, position INT64)",
    "CREATE REL TABLE IF NOT EXISTS CITES(FROM Paper TO Paper, first_seen STRING)",
    "CREATE REL TABLE IF NOT EXISTS PUBLISHED_IN(FROM Paper TO Venue)",
    "CREATE REL TABLE IF NOT EXISTS BELONGS_TO(FROM Paper TO Topic, added_at STRING)",
)

_UPSERT_PAPER = (
    "MERGE (p:Paper {paper_id: $paper_id}) "
    "SET p.title = $title, p.year = $year, p.source = $source, "
    "p.venue_id = $venue_id, p.discovered_at = $discovered_at"
)
_UPSERT_AUTHOR = (
    "MERGE (a:Author {author_id: $author_id}) SET a.name = $name, a.name_norm = $name_norm"
)
_UPSERT_CITATION = (
    "MATCH (a:Paper {paper_id: $citing_id}), (b:Paper {paper_id: $cited_id}) "
    "MERGE (a)-[e:CITES]->(b) "
    "SET e.first_seen = $first_seen"
)
_UPSERT_AUTHORSHIP = (
    "MATCH (p:Paper {paper_id: $paper_id}), (a:Author {author_id: $author_id}) "
    "MERGE (p)-[e:PAPER_AUTHOR {position: $position}]->(a)"
)


class GraphStore:
    """Kuzu 连接包装。用作上下文管理器，退出即 close（触发落盘）。"""

    def __init__(self, db_path: str | Path) -> None:
        self.path = Path(db_path)
        self._db: Any = None
        self._conn: Any = None

    # ------------------------------------------------------------------ #
    # 生命周期
    # ------------------------------------------------------------------ #
    @classmethod
    def open(cls, settings: Settings) -> GraphStore:
        path = assert_ascii_path(settings.storage.kuzu_file, label="storage.kuzu_path")
        store = cls(path)
        store.connect()
        store.ensure_schema()
        return store

    def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(str(self.path))
        self._conn = kuzu.Connection(self._db)

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None
        if self._db is not None:
            self._db.close()  # 只有这里会 checkpoint 到磁盘
            self._db = None

    def __enter__(self) -> GraphStore:
        if self._conn is None:
            self.connect()
            self.ensure_schema()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # ------------------------------------------------------------------ #
    # schema 与写入
    # ------------------------------------------------------------------ #
    def ensure_schema(self) -> None:
        try:
            for statement in NODE_DDL + REL_DDL:
                self._conn.execute(statement)
        except RuntimeError as exc:  # 旧库 schema 不兼容
            raise LitError(
                E_STORE_SCHEMA_MISMATCH,
                f"Kuzu schema 初始化失败（{self.path}）：{exc}；请 `lit-agent stores rebuild --graph`",
                context={"path": str(self.path)},
            ) from None

    def upsert_papers(self, rows: Iterable[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self._conn.execute(_UPSERT_PAPER, dict(row))
            count += 1
        return count

    def upsert_authors(self, rows: Iterable[dict[str, Any]]) -> int:
        count = 0
        for row in rows:
            self._conn.execute(_UPSERT_AUTHOR, dict(row))
            count += 1
        return count

    def upsert_citations(self, pairs: Iterable[tuple[str, str]], *, first_seen: str) -> int:
        count = 0
        for citing, cited in pairs:
            if citing == cited:
                continue
            self._conn.execute(
                _UPSERT_CITATION, {"citing_id": citing, "cited_id": cited, "first_seen": first_seen}
            )
            count += 1
        return count

    def upsert_authorships(self, rows: Iterable[tuple[str, str, int]]) -> int:
        count = 0
        for paper_id, author_id, position in rows:
            self._conn.execute(
                _UPSERT_AUTHORSHIP,
                {"paper_id": paper_id, "author_id": author_id, "position": position},
            )
            count += 1
        return count

    # ------------------------------------------------------------------ #
    # 查询
    # ------------------------------------------------------------------ #
    def _scalar(self, statement: str, params: dict[str, Any] | None = None) -> int:
        result = self._conn.execute(statement, params or {})
        row = result.get_next()
        return int(row[0]) if row else 0

    def counts(self) -> dict[str, int]:
        return {
            "papers": self._scalar("MATCH (p:Paper) RETURN count(*)"),
            "authors": self._scalar("MATCH (a:Author) RETURN count(*)"),
            "citations": self._scalar("MATCH ()-[e:CITES]->() RETURN count(*)"),
            "authorships": self._scalar("MATCH ()-[e:PAPER_AUTHOR]->() RETURN count(*)"),
        }

    def cited_by(self, paper_id: str, *, limit: int = 50) -> list[str]:
        result = self._conn.execute(
            "MATCH (a:Paper)-[:CITES]->(b:Paper {paper_id: $paper_id}) "
            "RETURN a.paper_id LIMIT $limit",
            {"paper_id": paper_id, "limit": limit},
        )
        out: list[str] = []
        while result.has_next():
            out.append(str(result.get_next()[0]))
        return out

    def references_of(self, paper_id: str, *, limit: int = 200) -> list[str]:
        result = self._conn.execute(
            "MATCH (a:Paper {paper_id: $paper_id})-[:CITES]->(b:Paper) "
            "RETURN b.paper_id LIMIT $limit",
            {"paper_id": paper_id, "limit": limit},
        )
        out: list[str] = []
        while result.has_next():
            out.append(str(result.get_next()[0]))
        return out


def paper_rows(papers: Sequence[Any], *, discovered_at: str) -> list[dict[str, Any]]:
    """`Paper` → 图节点行（只取图里需要的字段，完整元数据留在 SQLite）。"""
    return [
        {
            "paper_id": paper.paper_id,
            "title": paper.title,
            "year": paper.year,
            "source": paper.source,
            "venue_id": paper.venue_id,
            "discovered_at": discovered_at,
        }
        for paper in papers
    ]

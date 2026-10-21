"""图谱映射 agent（S5）：把去重关系折叠成"论文簇"视图。

纯函数为主：`map_clusters()` 接收 (primary_id, merged_id) 关系；
`run()` 从库读取后交给纯函数，便于单测不依赖数据库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.session import connect, make_engine

__all__ = ["MapResult", "map_clusters", "run"]


@dataclass
class MapResult:
    clusters: dict[str, list[str]] = field(default_factory=dict)
    orphan_merges: list[str] = field(default_factory=list)

    @property
    def cluster_count(self) -> int:
        return len(self.clusters)

    @property
    def merged_count(self) -> int:
        return sum(len(members) for members in self.clusters.values())


def map_clusters(primary_ids: list[str], edges: list[tuple[str, str]]) -> MapResult:
    """返回 primary → [merged...]；primary 不在语料中的合并记为孤儿。"""
    known = set(primary_ids)
    clusters: dict[str, list[str]] = {}
    orphan: list[str] = []
    for primary, merged in edges:
        if primary not in known:
            orphan.append(f"{primary}->{merged}")
            continue
        clusters.setdefault(primary, []).append(merged)
    return MapResult(clusters=clusters, orphan_merges=orphan)


def run(state: dict[str, Any], *, settings: Settings, **_: Any) -> dict[str, Any]:
    engine = make_engine(settings)
    try:
        with connect(engine) as conn:
            primaries = [
                str(row[0])
                for row in conn.execute(
                    text(
                        "SELECT paper_id FROM papers"
                        " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)"
                    )
                ).all()
            ]
            edges = [
                (str(row[0]), str(row[1]))
                for row in conn.execute(
                    text("SELECT primary_id, merged_id FROM paper_merges")
                ).all()
            ]
    finally:
        engine.dispose()
    result = map_clusters(primaries, edges)
    return {
        "artifacts": {
            "clusters": result.cluster_count,
            "merged": result.merged_count,
            "orphans": len(result.orphan_merges),
        },
        "counters": {"clusters": result.cluster_count},
    }

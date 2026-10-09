"""归一化与去重（Phase 0 step 5.2；对应设计文档 D6 三段式去重）。

职责边界（防职责漂移，见 `docs/implementation/phase0-implementation-steps.md` §1.1.2）
- 本模块只做"记录 → 统一 `Paper`"的纯函数转换与去重判定，**不碰网络、不碰数据库、不写事件**。
- 调用方（steps/）负责抓取、落库与埋点。

设计要点
- `canonical_id` 优先级 = **DOI → OpenAlex W → arXiv → 标题指纹**（契约见 `models.Paper.paper_id`）。
- 去重按 **D6 三段式**：① 精确键（canonical id）② 指纹（归一化标题 + 年份 ±1 + 首作者归一化名）
  ③ 模糊确认（标题 token 集合相似度 ≥ 阈值）。**主记录与 `merged_ids` 都不删除**，只标记归属。
- 主记录选择**确定性**（先看有无摘要、再看有无 DOI、再看作者数、最后取字典序最小 id），
  保证"同样的输入必然选出同样的主记录"——这是可复现与幂等的前提。
- `Paper` 目前**没有** `merged_ids` 字段（改契约需 ADR，属 Phase 1）；本轮把合并关系作为
  去重结果单独返回，由调用方落到 `paper_merges` 表并在报告脚注披露。
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from .models import Author, Paper

__all__ = [
    "DedupResult",
    "canonical_id",
    "dedup_papers",
    "name_norm",
    "normalize_doi",
    "openalex_work_to_paper",
    "reconstruct_abstract",
    "similar_title",
    "title_norm",
    "to_author",
]

_NON_WORD = re.compile(r"[^\w\s]+", re.UNICODE)
_SPACES = re.compile(r"\s+")
_DOI_URL = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)", re.IGNORECASE)
_OPENALEX_URL = re.compile(r"^https?://openalex\.org/", re.IGNORECASE)


def normalize_doi(doi: str | None) -> str | None:
    """去掉 URL 前缀、统一小写；空值返回 None。"""
    if not doi:
        return None
    value = _DOI_URL.sub("", doi.strip()).strip()
    if not value or not value.lower().startswith("10."):
        return None
    return value.lower()


def _strip_accents(text: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch)
    )


def name_norm(name: str) -> str:
    """作者名归一化（消歧**预留**，本轮不做消歧）：小写、去音标、去标点、压空白。"""
    value = _strip_accents(name or "").lower()
    value = _NON_WORD.sub(" ", value)
    return _SPACES.sub(" ", value).strip()


def title_norm(title: str) -> str:
    """标题归一化：小写、去音标、去标点、压空白（去重指纹的第一分量）。"""
    return name_norm(title)


def canonical_id(
    *,
    doi: str | None = None,
    openalex_id: str | None = None,
    arxiv_id: str | None = None,
    title: str | None = None,
    year: int | None = None,
) -> str:
    """按契约优先级生成 canonical id；全部缺失时退回标题指纹（保证仍有稳定键）。"""
    normalized_doi = normalize_doi(doi)
    if normalized_doi:
        return normalized_doi
    if openalex_id:
        value = _OPENALEX_URL.sub("", openalex_id.strip())
        if value:
            return value
    if arxiv_id:
        value = arxiv_id.strip()
        if value:
            return value if value.startswith("arxiv:") else f"arxiv:{value}"
    if title:
        digest = abs(hash(f"{title_norm(title)}|{year or ''}")) % (2**40)
        return f"title:{digest:010x}"
    raise ValueError("canonical_id 需要至少一个可用标识（doi/openalex_id/arxiv_id/title）")


def _tokens(text: str) -> frozenset[str]:
    return frozenset(t for t in title_norm(text).split() if len(t) > 2)


def similar_title(left: str, right: str) -> float:
    """标题 token 集合相似度（0..1）；用 Jaccard，短标题退化为包含判断。"""
    a, b = _tokens(left), _tokens(right)
    if not a or not b:
        return 0.0
    inter = len(a & b)
    return inter / len(a | b)


@dataclass
class DedupResult:
    """去重结果：主记录 + 合并关系 + 统计（`Paper` 无 `merged_ids`，故单独返回）。"""

    unique: list[Paper]
    merged: dict[str, list[str]] = field(default_factory=dict)
    stats: dict[str, Any] = field(default_factory=dict)


def _primary_rank(paper: Paper) -> tuple[int, int, int, str]:
    """主记录排序键（越小越优先）：有摘要 > 有 DOI > 作者多 > id 字典序。"""
    return (
        0 if paper.abstract.strip() else 1,
        0 if normalize_doi(paper.paper_id) else 1,
        -len(paper.authors),
        paper.paper_id,
    )


@dataclass
class _Cluster:
    """一个聚类：代表记录 + 成员 + 被合并的 id（含第 1 段精确键产生的同 id 重复）。"""

    members: list[Paper]
    merged: list[str] = field(default_factory=list)

    @property
    def representative(self) -> Paper:
        return min(self.members, key=_primary_rank)

    @property
    def years(self) -> set[int]:
        return {p.year for p in self.members if p.year is not None}

    @property
    def first_author(self) -> str:
        rep = self.representative
        return rep.authors[0].name_norm if rep.authors else ""


def _same_paper(cluster: _Cluster, paper: Paper, fuzzy_min: float) -> bool:
    """指纹匹配 + 模糊确认：标题相似、首作者相同、年份不冲突（±1 内视为同一版本）。"""
    rep = cluster.representative
    if similar_title(rep.title, paper.title) < fuzzy_min:
        return False
    first = paper.authors[0].name_norm if paper.authors else ""
    if first and cluster.first_author and first != cluster.first_author:
        return False
    year_conflict = (
        paper.year is not None
        and bool(cluster.years)
        and min(abs(paper.year - y) for y in cluster.years) > 1
    )
    return not year_conflict


def dedup_papers(papers: Iterable[Paper], *, fuzzy_min: float = 0.9) -> DedupResult:
    """D6 三段式去重：① 精确键 ② 指纹（标题+年份±1+首作者）③ 模糊相似度确认。"""
    records = list(papers)

    # 第 1 段：精确键（同一 canonical id 的多条记录合成一组）
    exact: dict[str, list[Paper]] = {}
    for paper in records:
        exact.setdefault(paper.paper_id, []).append(paper)

    # 第 2/3 段：按确定性顺序聚类
    clusters: list[_Cluster] = []
    for group in sorted(exact.values(), key=lambda g: _primary_rank(min(g, key=_primary_rank))):
        extra_merged = [p.paper_id for p in group[1:]]
        representative = group[0]
        placed = False
        for cluster in clusters:
            if _same_paper(cluster, representative, fuzzy_min):
                cluster.members.extend(group)
                cluster.merged.extend(extra_merged)
                placed = True
                break
        if not placed:
            clusters.append(_Cluster(members=list(group), merged=extra_merged))

    unique: list[Paper] = []
    merged_map: dict[str, list[str]] = {}
    same_id_rows = 0
    for cluster in clusters:
        primary = cluster.representative
        unique.append(primary)
        # 被合并者 = 第 1 段同 id 重复 + 聚类内其他成员（主记录自身除外）
        others = [p.paper_id for p in cluster.members if p.paper_id != primary.paper_id]
        extras = sorted(set(cluster.merged) | set(others))
        extras = [pid for pid in extras if pid != primary.paper_id]
        if extras:
            merged_map[primary.paper_id] = extras
        # 同 canonical id 的重复行**不算**"合并了不同 id"（语义不同：那是重复抓取，不是版本合并）
        same_id_rows += sum(1 for p in cluster.members[1:] if p.paper_id == primary.paper_id)

    stats = {
        "input": len(records),
        "unique": len(unique),
        "merged_version_copies": sum(len(v) for v in merged_map.values()),
        "dropped_same_id_rows": same_id_rows,
        "duplicate_rate": round(1 - len(unique) / len(records), 4) if records else 0.0,
        "fuzzy_min": fuzzy_min,
    }
    return DedupResult(unique=unique, merged=merged_map, stats=stats)


def to_author(raw: dict[str, Any]) -> Author:
    """从 OpenAlex `authorships` 条目构造 `Author`（源内 id 优先，缺失时用 name_norm 派生）。"""
    display = (raw.get("author") or {}).get("display_name") or ""
    source_id = (raw.get("author") or {}).get("id") or ""
    author_id = _OPENALEX_URL.sub("", source_id.strip()) or f"name:{name_norm(display)}"
    return Author(
        author_id=author_id, name=display or author_id, name_norm=name_norm(display) or author_id
    )


def reconstruct_abstract(inverted_index: dict[str, list[int]] | None) -> str:
    """OpenAlex 的 `abstract_inverted_index` 还原为正文（词 → 位置列表）。"""
    if not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, indexes in inverted_index.items():
        for idx in indexes:
            positions.append((int(idx), word))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def openalex_work_to_paper(work: dict[str, Any], *, source: str = "openalex") -> Paper:
    """OpenAlex `work` → 统一 `Paper`（契约字段见 `models.Paper`）。"""
    doi = work.get("doi")
    openalex_id = work.get("id")
    paper_id = canonical_id(
        doi=doi,
        openalex_id=openalex_id,
        title=work.get("title") or work.get("display_name"),
        year=work.get("publication_year"),
    )
    primary = work.get("primary_location") or {}
    venue = ((primary.get("source") or {}) or {}).get("display_name")
    oa = work.get("best_oa_location") or work.get("primary_location") or {}
    references = [
        _OPENALEX_URL.sub("", ref.strip()) for ref in (work.get("referenced_works") or []) if ref
    ]
    year = work.get("publication_year")
    return Paper(
        paper_id=paper_id,
        title=(work.get("title") or work.get("display_name") or paper_id).strip(),
        abstract=reconstruct_abstract(work.get("abstract_inverted_index")),
        authors=[to_author(a) for a in (work.get("authorships") or [])],
        venue=venue,
        year=int(year) if year else None,
        source=source,
        references=references,
        oa_pdf_url=oa.get("pdf_url") or oa.get("landing_page_url"),
    )

"""S1b 数据源策略可行性（Phase 0 Spike 1 的衍生）。

要回答的四个问题
    1) **白名单过滤后**的引用完整率是多少（宽召回样本只有 ~18%，过滤后可能显著更高）？
    2) **去重方案**是否可行：同标题/同 DOI 的多版本有多少？指纹去重后还剩多少唯一论文？
    3) **检索策略**怎么选：宽召回 / 白名单过滤 / 多查询扩展并集，产出量与重叠如何？
    4) **增量游标**语义：按 `updated` 拉取是否可用？游标分页是否稳定？是否有回溯更新？

产出
    out/s1b_records.csv    所有抓取记录（带 strategy / 去重标记）
    out/s1b_summary.json   四项结论 + 数字 + 证据
    out/events.jsonl、logs/app.jsonl  （与 run_id 关联）

用法
    uv run python steps/s1b_retrieval_and_dedup.py --topics T1,T2 --years 3 --per-page 100
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx  # noqa: E402
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

OPENALEX_API = "https://api.openalex.org/works"
OPENALEX_SOURCES = "https://api.openalex.org/sources"
HTTP_TIMEOUT = 30.0
HTTP_RETRIES = 3
SELECT_FIELDS = (
    "id,doi,title,publication_year,publication_date,updated_date,"
    "referenced_works,authorships,primary_location,best_oa_location,open_access,type"
)

TOPICS: dict[str, dict[str, Any]] = {
    "T1": {
        "name": "multi-agent LLM orchestration reliability",
        "expansion_queries": [
            "multi-agent LLM orchestration",
            "LLM agent reliability self-correction",
            "agent runtime guardrail failure recovery",
        ],
    },
    "T2": {
        "name": "quantized vision-language model deployment on edge devices",
        "expansion_queries": [
            "quantized vision language model edge",
            "VLM quantization edge deployment",
            "efficient multimodal model inference embedded",
        ],
    },
}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title(value: str | None) -> str:
    return _NON_ALNUM.sub(" ", (value or "").lower()).strip()


def short_id(value: str | None) -> str:
    return (value or "").rsplit("/", 1)[-1]


def retry_get(client: httpx.Client, url: str, params: dict[str, Any]) -> dict[str, Any]:
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            response = client.get(url, params=params)
            if response.status_code < 400:
                return response.json()
            last_error = RuntimeError(f"HTTP {response.status_code}: {response.text[:120]}")
        except httpx.HTTPError as exc:
            last_error = exc
        if attempt < HTTP_RETRIES:
            time.sleep(1.5**attempt)
    raise RuntimeError(f"请求失败（重试 {HTTP_RETRIES} 次）：{last_error}")


# --------------------------------------------------------------------------- #
# 抓取
# --------------------------------------------------------------------------- #
def fetch_works(
    client: httpx.Client,
    *,
    mailto: str,
    query: str,
    year_filter: str,
    venue_ids: list[str] | None,
    per_page: int,
    pages: int = 1,
) -> list[dict[str, Any]]:
    """按策略抓取；whitelist 策略传入 venue_ids，broad 策略传 None。"""
    filters = [year_filter]
    if venue_ids is not None:
        filters.append("primary_location.source.id:" + "|".join(venue_ids))
    collected: list[dict[str, Any]] = []
    for page in range(1, pages + 1):
        payload = retry_get(
            client,
            OPENALEX_API,
            {
                "search": query,
                "filter": ",".join(filters),
                "per-page": per_page,
                "page": page,
                "select": SELECT_FIELDS,
                "mailto": mailto,
            },
        )
        results = payload.get("results", [])
        collected.extend(results)
        if len(results) < per_page:
            break
        time.sleep(0.2)
    return collected


def to_record(raw: dict[str, Any], *, topic: str, strategy: str) -> dict[str, Any]:
    venue = ((raw.get("primary_location") or {}).get("source") or {}).get("display_name") or ""
    oa = raw.get("best_oa_location") or {}
    return {
        "topic": topic,
        "strategy": strategy,
        "paper_id": short_id(raw.get("id")),
        "doi": (raw.get("doi") or "").replace("https://doi.org/", ""),
        "title": raw.get("title") or raw.get("display_name") or "",
        "title_norm": normalize_title(raw.get("title") or raw.get("display_name")),
        "year": raw.get("publication_year"),
        "venue": venue,
        "has_references": bool(raw.get("referenced_works")),
        "is_oa": bool(oa.get("pdf_url") or oa.get("landing_page_url"))
        or bool((raw.get("open_access") or {}).get("is_oa")),
        "authors_count": len(raw.get("authorships") or []),
    }


# --------------------------------------------------------------------------- #
# 统计
# --------------------------------------------------------------------------- #
def dedup_stats(records: list[dict[str, Any]]) -> dict[str, Any]:
    """按归一化标题与 DOI 统计重复；给出唯一论文数。"""
    by_title: dict[str, list[dict[str, Any]]] = {}
    by_doi: dict[str, list[dict[str, Any]]] = {}
    for row in records:
        by_title.setdefault(row["title_norm"], []).append(row)
        if row["doi"]:
            by_doi.setdefault(row["doi"], []).append(row)

    title_dupes = {key: rows for key, rows in by_title.items() if len(rows) > 1 and key}
    doi_dupes = {key: rows for key, rows in by_doi.items() if len(rows) > 1}
    # 版本副本：同标题、不同 paper_id（Zenodo/出版方/arXiv 各一份常见）
    version_copies = sum(len(rows) - 1 for rows in title_dupes.values())
    return {
        "records": len(records),
        "unique_titles": len(by_title),
        "unique_dois": len(by_doi),
        "duplicate_title_groups": len(title_dupes),
        "duplicate_doi_groups": len(doi_dupes),
        "version_copies": version_copies,
        "duplicate_rate_by_title": round(version_copies / len(records), 4) if records else None,
        "example_duplicate_titles": [
            rows[0]["title"][:80] for rows in list(title_dupes.values())[:3]
        ],
    }


def completeness(records: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(records)
    if not total:
        return {"n": 0}
    return {
        "n": total,
        "references_completeness": round(sum(1 for r in records if r["has_references"]) / total, 4),
        "oa_availability": round(sum(1 for r in records if r["is_oa"]) / total, 4),
        "unique_titles": len({r["title_norm"] for r in records}),
    }


def jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 1.0
    return round(len(left & right) / len(left | right), 4)


def incremental_probe(client: httpx.Client, *, mailto: str, days: int = 30) -> dict[str, Any]:
    """增量语义探测：`from_updated_date` 是否可用；不可用时用 `from_publication_date` 倒序水位线替代。"""
    since = (datetime.now(UTC) - timedelta(days=days)).strftime("%Y-%m-%d")
    result: dict[str, Any] = {"since_date": since, "checked_at": datetime.now(UTC).isoformat()}

    # ① 首选：按 updated_date 增量（实测为付费能力，记录结论而不是让脚本崩）
    updated_params = {
        "filter": f"from_updated_date:{since}",
        "per-page": 25,
        "select": SELECT_FIELDS,
        "mailto": mailto,
    }
    try:
        first = retry_get(client, OPENALEX_API, {**updated_params, "cursor": "*"})
        page_one_ids = [short_id(item.get("id")) for item in first.get("results", [])]
        repeat = retry_get(client, OPENALEX_API, {**updated_params, "cursor": "*"})
        repeat_ids = [short_id(item.get("id")) for item in repeat.get("results", [])]
        cursor = (first.get("meta") or {}).get("next_cursor")
        second = (
            retry_get(client, OPENALEX_API, {**updated_params, "cursor": cursor})
            if cursor
            else {"results": []}
        )
        retro = 0
        for item in first.get("results", []):
            published, updated = item.get("publication_date"), item.get("updated_date")
            if published and updated and updated[:10] > published[:10]:
                delta = (
                    datetime.fromisoformat(updated[:10]) - datetime.fromisoformat(published[:10])
                ).days
                if delta > 30:
                    retro += 1
        result.update(
            {
                "updated_filter_available": True,
                "page1_count": len(page_one_ids),
                "paging_stable": page_one_ids == repeat_ids,
                "page2_count": len([short_id(i.get("id")) for i in second.get("results", [])]),
                "retro_updated_gt_30d": retro,
                "retro_share": round(retro / len(page_one_ids), 4) if page_one_ids else None,
            }
        )
    except RuntimeError as exc:
        result["updated_filter_available"] = False
        result["updated_filter_error"] = str(exc)[:200]

    # ② 替代：publication_date 倒序 + 游标分页（用"已知 id 水位线"实现增量）
    pub_params = {
        "filter": f"from_publication_date:{since}",
        "sort": "publication_date:desc",
        "per-page": 25,
        "select": SELECT_FIELDS,
        "mailto": mailto,
    }
    try:
        page1 = retry_get(client, OPENALEX_API, {**pub_params, "cursor": "*"})
        page1_ids = [short_id(item.get("id")) for item in page1.get("results", [])]
        page1_repeat = retry_get(client, OPENALEX_API, {**pub_params, "cursor": "*"})
        page1_repeat_ids = [short_id(item.get("id")) for item in page1_repeat.get("results", [])]
        next_cursor = (page1.get("meta") or {}).get("next_cursor")
        page2 = (
            retry_get(client, OPENALEX_API, {**pub_params, "cursor": next_cursor})
            if next_cursor
            else {"results": []}
        )
        page2_ids = [short_id(item.get("id")) for item in page2.get("results", [])]
        dates = [
            item.get("publication_date")
            for item in page1.get("results", [])
            if item.get("publication_date")
        ]
        result.update(
            {
                "publication_filter_available": True,
                "publication_page1_count": len(page1_ids),
                "publication_paging_stable": page1_ids == page1_repeat_ids,
                "publication_page2_count": len(page2_ids),
                "publication_page_overlap": len(set(page1_ids) & set(page2_ids)),
                "newest_publication_date": max(dates) if dates else None,
                "oldest_on_page1": min(dates) if dates else None,
            }
        )
    except RuntimeError as exc:
        result["publication_filter_available"] = False
        result["publication_filter_error"] = str(exc)[:200]

    return result


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Spike S1b：检索策略 / 去重 / 引用完整率")
    parser.add_argument("--topics", default="T1,T2")
    parser.add_argument("--years", type=int, default=3)
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--out", default="out/s1b_records.csv")
    parser.add_argument("--summary", default="out/s1b_summary.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    setup_logging(settings)
    venue_ids = list(settings.sources.venues)
    if not venue_ids:
        print(
            "[FAIL] config.sources.venues 为空：请先填入 OpenAlex source id 白名单", file=sys.stderr
        )
        return 2

    run_id = f"p0-s1b-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    log = open_event_log(settings.paths.out_dir / "events.jsonl", run_id=run_id)
    clear_context()
    bind_context(run_id=run_id, stage="S1b_source_strategy", agent="single")
    since_year = datetime.now(UTC).year - args.years
    year_filter = f"publication_year:>{since_year}"
    mailto = settings.sources.openalex_mailto
    topic_ids = [item.strip() for item in args.topics.split(",") if item.strip()]

    log_event(
        Severity.INFO,
        "spike_started",
        "S1b 检索策略/去重/引用完整率 验证开始",
        venues=len(venue_ids),
        topics=topic_ids,
    )
    log.emit(EventType.PHASE_CHANGE, payload={"spike": "S1b", "venues": len(venue_ids)})

    records: list[dict[str, Any]] = []
    per_topic: dict[str, Any] = {}
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for topic_id in topic_ids:
            topic = TOPICS.get(topic_id)
            if topic is None:
                log_event(Severity.WARNING, "topic_unknown", "未知 topic，跳过", topic=topic_id)
                continue

            # 策略 1：宽召回（无 venue 过滤）
            broad = [
                to_record(raw, topic=topic_id, strategy="broad")
                for raw in fetch_works(
                    client,
                    mailto=mailto,
                    query=topic["name"],
                    year_filter=year_filter,
                    venue_ids=None,
                    per_page=args.per_page,
                )
            ]
            # 策略 2：白名单过滤
            whitelist = [
                to_record(raw, topic=topic_id, strategy="whitelist")
                for raw in fetch_works(
                    client,
                    mailto=mailto,
                    query=topic["name"],
                    year_filter=year_filter,
                    venue_ids=venue_ids,
                    per_page=args.per_page,
                    pages=2,
                )
            ]
            # 策略 3：查询扩展并集（白名单过滤）
            expansion_raw: list[dict[str, Any]] = []
            for query in topic["expansion_queries"]:
                expansion_raw.extend(
                    fetch_works(
                        client,
                        mailto=mailto,
                        query=query,
                        year_filter=year_filter,
                        venue_ids=venue_ids,
                        per_page=args.per_page,
                    )
                )
            expansion = [
                to_record(raw, topic=topic_id, strategy="expansion") for raw in expansion_raw
            ]

            pool = broad + whitelist + expansion
            records.extend(pool)
            broad_titles = {row["title_norm"] for row in broad}
            whitelist_titles = {row["title_norm"] for row in whitelist}
            expansion_titles = {row["title_norm"] for row in expansion}
            per_topic[topic_id] = {
                "broad": completeness(broad),
                "whitelist": completeness(whitelist),
                "expansion": completeness(expansion),
                "overlap_broad_whitelist": jaccard(broad_titles, whitelist_titles),
                "whitelist_extra_over_broad": len(whitelist_titles - broad_titles),
                "expansion_extra_over_whitelist": len(expansion_titles - whitelist_titles),
                "dedup": dedup_stats(pool),
            }
            log_event(
                Severity.INFO,
                "strategy_compared",
                "检索策略对比完成",
                topic=topic_id,
                whitelist_n=per_topic[topic_id]["whitelist"]["n"],
                refs_whitelist=per_topic[topic_id]["whitelist"].get("references_completeness"),
                refs_broad=per_topic[topic_id]["broad"].get("references_completeness"),
                dup_rate=per_topic[topic_id]["dedup"]["duplicate_rate_by_title"],
            )
            log.emit(
                EventType.METRIC,
                payload={
                    "topic": topic_id,
                    "refs_whitelist": per_topic[topic_id]["whitelist"].get(
                        "references_completeness"
                    ),
                    "dup_rate": per_topic[topic_id]["dedup"]["duplicate_rate_by_title"],
                },
            )

        incremental = incremental_probe(client, mailto=mailto)

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "since_year": since_year,
        "venue_count": len(venue_ids),
        "topics": per_topic,
        "incremental_probe": incremental,
    }
    out_dir = settings.paths.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = settings.paths.out_dir.parent / args.out
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(records[0].keys()) if records else ["topic"]
        )
        writer.writeheader()
        writer.writerows(records)
    summary_path = settings.paths.out_dir.parent / args.summary
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"run_id    {run_id}")
    print(f"records   {len(records)} -> {csv_path}")
    for topic_id, data in per_topic.items():
        print(
            f"{topic_id}: broad n={data['broad']['n']} refs={data['broad'].get('references_completeness')} | "
            f"whitelist n={data['whitelist']['n']} refs={data['whitelist'].get('references_completeness')} "
            f"oa={data['whitelist'].get('oa_availability')} | "
            f"expansion n={data['expansion']['n']} refs={data['expansion'].get('references_completeness')} | "
            f"dup_rate={data['dedup']['duplicate_rate_by_title']} "
            f"unique={data['dedup']['unique_titles']}/{data['dedup']['records']}"
        )
    print(
        "incremental: "
        f"updated_filter_available={incremental.get('updated_filter_available')} "
        f"publication_filter_available={incremental.get('publication_filter_available')} "
        f"pub_page1={incremental.get('publication_page1_count')} "
        f"pub_stable={incremental.get('publication_paging_stable')} "
        f"pub_page2={incremental.get('publication_page2_count')} "
        f"pub_overlap={incremental.get('publication_page_overlap')} "
        f"newest={incremental.get('newest_publication_date')}"
    )
    if incremental.get("updated_filter_error"):
        print(f"incremental_note: {incremental['updated_filter_error']}")
    print(f"summary   {summary_path}")
    log_event(Severity.INFO, "spike_finished", "S1b 完成", records=len(records))
    clear_context()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""S1 源覆盖度验证（Phase 0 Spike 1）。

要回答的问题
    以 OpenAlex 为主、arXiv 为辅，能否覆盖目标方向（CS / 软硬件 / 工科）？
    "只用 OpenAlex 会漏什么？arXiv 补上多少？"

产出（可追溯）
    out/s1_coverage.csv    每篇论文一行（含是否白名单 venue / 是否 OA / 是否有引用字段）
    out/s1_coverage.json   四项指标 + 抽查结果 + 限速探测结果 + 结论
    out/events.jsonl       工具调用与指标事件（与日志用 run_id 关联）
    logs/app.jsonl         过程日志

指标定义（每 topic）
    venue 覆盖率   = 白名单 venue 命中数 / 有 venue 信息的总数
    引用完整率     = referenced_works 非空的论文数 / 总数
    OA 可得率      = 有 OA 全文定位（best_oa_location 或 open_access.is_oa）的论文数 / 总数
    arXiv 补漏率   = arXiv 结果中未出现在 OpenAlex 结果里的比例（按 DOI 或归一化标题匹配）

用法
    uv run python steps/s1_source_coverage.py --topics T1,T2 --years 3 --limit 200
    uv run python steps/s1_source_coverage.py --skip-probe      # 跳过限速探测
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # 允许 `python steps/xxx.py` 直接运行

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
HTTP_TIMEOUT = 30.0
HTTP_RETRIES = 3

#: 候选测试 topic（英文；用于 Phase 0 验证，不是最终评测 topic 集）
TOPICS: dict[str, dict[str, Any]] = {
    "T1": {
        "name": "multi-agent LLM orchestration reliability",
        "openalex_queries": [
            "multi-agent LLM orchestration",
            "LLM agent reliability self-correction",
        ],
        "arxiv_query": 'all:"multi-agent" AND all:"large language model"',
        "arxiv_categories": ["cs.AI", "cs.LG", "cs.MA", "cs.SE"],
    },
    "T2": {
        "name": "quantized vision-language model deployment on edge devices",
        "openalex_queries": [
            "quantized vision language model edge",
            "VLM quantization edge deployment",
        ],
        "arxiv_query": 'all:"vision-language model" AND all:"quantization"',
        "arxiv_categories": ["cs.CV", "cs.LG", "cs.AR"],
    },
}

#: venue 白名单（按归一化子串匹配；正式配置在 config.sources.venues 中以 OpenAlex source id 表达）
VENUE_WHITELIST = [
    "neurips",
    "nips",
    "icml",
    "iclr",
    "aaai",
    "ijcai",
    "acl",
    "emnlp",
    "naacl",
    "cvpr",
    "iccv",
    "eccv",
    "osdi",
    "sosp",
    "asplos",
    "isca",
    "micro",
    "hpca",
    "sigcomm",
    "nsdi",
    "icse",
    "fse",
    "ase",
    "dac",
    "iccad",
    "date",
    "tpami",
    "tnnls",
    "tip",
    "tcad",
    "tpds",
    "tse",
    "tmc",
    "jsac",
    "ieee transactions",
    "acm transactions",
]

#: 用于"白名单是否够用"的核心 venue 子集（解析为 OpenAlex source id 后做过滤计数）
VENUE_SUFFICIENCY_TOKENS = [
    "neurips",
    "icml",
    "iclr",
    "aaai",
    "ijcai",
    "acl",
    "emnlp",
    "cvpr",
    "iccv",
    "osdi",
    "sosp",
    "icse",
]

_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_title(value: str) -> str:
    return _NON_ALNUM.sub(" ", (value or "").lower()).strip()


def normalize_venue(value: str | None) -> str:
    return (value or "").lower()


def is_whitelisted_venue(venue: str | None) -> bool:
    if not venue:
        return False
    normalized = normalize_venue(venue)
    return any(token in normalized for token in VENUE_WHITELIST)


def short_id(openalex_id: str | None) -> str:
    return (openalex_id or "").rsplit("/", 1)[-1]


# --------------------------------------------------------------------------- #
# 源访问（OpenAlex 优先 pyalex，失败回退 httpx；arXiv 用官方客户端）
# --------------------------------------------------------------------------- #
def fetch_openalex(query: str, *, since_year: int, limit: int, mailto: str) -> list[dict[str, Any]]:
    """返回 OpenAlex works（原始 JSON dict 列表）。"""
    try:
        from pyalex import Works
        from pyalex import config as pyalex_config

        pyalex_config.email = mailto
        results = (
            Works()
            .search(query)
            .filter(publication_year=f">{since_year}")
            .get(per_page=min(limit, 200))
        )
        log_event(
            Severity.INFO,
            "source_call_finished",
            "openalex via pyalex",
            source="openalex",
            client="pyalex",
            query=query,
            results=len(results),
        )
        return list(results)
    except Exception as exc:  # noqa: BLE001 - pyalex 不可用时回退 httpx
        log_event(
            Severity.WARNING,
            "source_client_fallback",
            "pyalex 不可用，回退 httpx",
            source="openalex",
            error=str(exc)[:200],
        )

    params = {
        "search": query,
        "filter": f"publication_year:>{since_year}",
        "per-page": min(limit, 200),
        "mailto": mailto,
    }
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        response = request_with_retry(client, OPENALEX_API, params=params)
        payload = response.json()
    results = payload.get("results", [])
    log_event(
        Severity.INFO,
        "source_call_finished",
        "openalex via httpx",
        source="openalex",
        client="httpx",
        query=query,
        results=len(results),
    )
    return results


def request_with_retry(
    client: httpx.Client, url: str, *, params: dict[str, Any] | None = None
) -> httpx.Response:
    """带指数退避的 GET；4xx/5xx 与网络错误均重试有限次。"""
    last_error: Exception | None = None
    for attempt in range(1, HTTP_RETRIES + 1):
        try:
            response = client.get(url, params=params)
            if response.status_code < 400:
                return response
            last_error = httpx.HTTPStatusError(
                f"HTTP {response.status_code}", request=response.request, response=response
            )
        except httpx.HTTPError as exc:  # 网络/超时
            last_error = exc
        if attempt < HTTP_RETRIES:
            backoff = 1.5**attempt
            log_event(
                Severity.WARNING,
                "source_retry",
                f"第 {attempt} 次请求失败，{backoff:.1f}s 后重试",
                url=url,
                attempt=attempt,
                error=str(last_error)[:160],
            )
            time.sleep(backoff)
    raise RuntimeError(f"请求失败（重试 {HTTP_RETRIES} 次）：{url} -> {last_error}")


def fetch_arxiv(query: str, *, since_year: int, limit: int) -> list[dict[str, Any]]:
    import arxiv

    client = arxiv.Client(page_size=100, delay_seconds=1.0, num_retries=3)
    search = arxiv.Search(
        query=query,
        max_results=limit,
        sort_by=arxiv.SortCriterion.SubmittedDate,
    )
    rows: list[dict[str, Any]] = []
    for result in client.results(search):
        if result.published.year < since_year:
            continue
        rows.append(
            {
                "paper_id": short_id(result.entry_id),
                "title": result.title,
                "year": result.published.year,
                "venue": result.journal_ref,
                "doi": result.doi,
                "authors_count": len(result.authors),
                "categories": list(result.categories),
                "pdf_url": result.pdf_url,
            }
        )
    log_event(
        Severity.INFO,
        "source_call_finished",
        "arxiv search",
        source="arxiv",
        query=query,
        results=len(rows),
    )
    return rows


def rate_limit_probe(mailto: str, *, rounds: int = 20) -> dict[str, Any]:
    """礼貌限速探测：连续 N 次轻量请求，确认无封禁/无限流。"""
    statuses: list[int] = []
    latencies: list[float] = []
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for _ in range(rounds):
            started = time.perf_counter()
            response = client.get(
                OPENALEX_API,
                params={"per-page": 1, "mailto": mailto, "filter": "publication_year:>2024"},
            )
            latencies.append((time.perf_counter() - started) * 1000)
            statuses.append(response.status_code)
            time.sleep(0.2)
    return {
        "rounds": rounds,
        "status_counts": {str(code): statuses.count(code) for code in sorted(set(statuses))},
        "rate_limited": sum(1 for code in statuses if code == 429),
        "latency_ms_p50": round(sorted(latencies)[len(latencies) // 2], 1),
        "latency_ms_max": round(max(latencies), 1),
    }


def resolve_venue_source_ids(mailto: str, tokens: list[str] | None = None) -> dict[str, str]:
    """把 venue 名字解析为 OpenAlex source id（用于"白名单够不够用"的过滤计数）。"""
    resolved: dict[str, str] = {}
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for token in tokens or VENUE_SUFFICIENCY_TOKENS:
            try:
                response = request_with_retry(
                    client,
                    "https://api.openalex.org/sources",
                    params={"search": token, "per-page": 1, "mailto": mailto},
                )
            except Exception as exc:  # noqa: BLE001 - 单个 venue 解析失败不影响整体
                log_event(
                    Severity.WARNING,
                    "venue_resolve_failed",
                    "venue 解析失败",
                    token=token,
                    error=str(exc)[:120],
                )
                continue
            results = response.json().get("results", [])
            if results:
                resolved[short_id(results[0]["id"])] = results[0].get("display_name") or token
    return resolved


def venue_sufficiency(
    queries: list[str], source_ids: list[str], *, since_year: int, mailto: str
) -> dict[str, Any]:
    """白名单 venue 过滤后，各查询能召回多少篇（判断白名单能否作为主过滤器）。"""
    if not source_ids:
        return {"error": "未解析到任何 venue source id"}
    filter_expr = (
        "primary_location.source.id:" + "|".join(source_ids) + f",publication_year:>{since_year}"
    )
    per_query: list[dict[str, Any]] = []
    counts: list[int] = []
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for query in queries:
            try:
                response = request_with_retry(
                    client,
                    OPENALEX_API,
                    params={
                        "search": query,
                        "filter": filter_expr,
                        "per-page": 1,
                        "mailto": mailto,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                per_query.append({"query": query, "count": None, "error": str(exc)[:120]})
                continue
            count = int(response.json().get("meta", {}).get("count", 0))
            counts.append(count)
            per_query.append({"query": query, "count": count})
    years = max(1, datetime.now(UTC).year - since_year)
    return {
        "venues_resolved": len(source_ids),
        "queries": per_query,
        "total_matched": sum(counts),
        "per_year_estimate": round(sum(counts) / years, 1),
        "min_query_count": min(counts) if counts else 0,
    }


def openalex_existence_probe(
    rows: list[dict[str, Any]], *, mailto: str, sample_size: int = 30
) -> dict[str, Any]:
    """抽样检查 arXiv 论文在 OpenAlex 中是否存在（区分"未收录"与"本次宽召回没捞到"）。"""
    if not rows:
        return {"sampled": 0, "found": 0, "found_rate": None}
    step = max(1, len(rows) // sample_size)
    samples = rows[::step][:sample_size]
    found: list[str] = []
    missing: list[str] = []
    with httpx.Client(timeout=HTTP_TIMEOUT) as client:
        for row in samples:
            try:
                if row["doi"]:
                    params = {"filter": f"doi:{row['doi']}", "per-page": 1, "mailto": mailto}
                else:
                    words = normalize_title(row["title"]).split()[:8]
                    if not words:
                        continue
                    params = {"search": " ".join(words), "per-page": 1, "mailto": mailto}
                response = request_with_retry(client, OPENALEX_API, params=params)
                if response.json().get("results"):
                    found.append(row["title"][:70])
                else:
                    missing.append(row["title"][:70])
            except Exception:  # noqa: BLE001
                continue
            time.sleep(0.2)
    total = len(found) + len(missing)
    return {
        "sampled": total,
        "found": len(found),
        "found_rate": round(len(found) / total, 4) if total else None,
        "missing_examples": missing[:5],
    }


# --------------------------------------------------------------------------- #
# 归一化与统计
# --------------------------------------------------------------------------- #
def openalex_to_row(record: dict[str, Any], topic_id: str) -> dict[str, Any]:
    venue = ((record.get("primary_location") or {}).get("source") or {}).get("display_name")
    oa_location = record.get("best_oa_location") or {}
    is_oa = bool(oa_location.get("pdf_url") or oa_location.get("landing_page_url")) or bool(
        (record.get("open_access") or {}).get("is_oa")
    )
    authorships = record.get("authorships") or []
    return {
        "topic": topic_id,
        "source": "openalex",
        "paper_id": short_id(record.get("id")),
        "title": record.get("title") or record.get("display_name") or "",
        "year": record.get("publication_year"),
        "venue": venue or "",
        "is_whitelist_venue": is_whitelisted_venue(venue),
        "has_references": bool(record.get("referenced_works")),
        "is_oa": is_oa,
        "oa_url": oa_location.get("pdf_url") or oa_location.get("landing_page_url") or "",
        "doi": (record.get("doi") or "").replace("https://doi.org/", ""),
        "authors_count": len(authorships),
        "type": record.get("type") or "",
    }


def arxiv_to_row(record: dict[str, Any], topic_id: str) -> dict[str, Any]:
    return {
        "topic": topic_id,
        "source": "arxiv",
        "paper_id": record["paper_id"],
        "title": record["title"],
        "year": record["year"],
        "venue": record["venue"] or "",
        "is_whitelist_venue": False,
        "has_references": False,  # arXiv API 不提供引用关系
        "is_oa": True,  # arXiv 全文默认可得
        "oa_url": record["pdf_url"] or "",
        "doi": record["doi"] or "",
        "authors_count": record["authors_count"],
        "type": "preprint",
    }


def summarize_topic(
    topic_id: str, rows: list[dict[str, Any]], arxiv_rows: list[dict[str, Any]]
) -> dict[str, Any]:
    total = len(rows)
    if total == 0:
        return {"topic": topic_id, "total": 0, "note": "OpenAlex 未返回结果"}

    venue_hits = sum(1 for row in rows if row["is_whitelist_venue"])
    ref_complete = sum(1 for row in rows if row["has_references"])
    oa_available = sum(1 for row in rows if row["is_oa"])

    openalex_titles = {normalize_title(row["title"]) for row in rows}
    openalex_dois = {row["doi"] for row in rows if row["doi"]}
    missed: list[dict[str, Any]] = []
    for row in arxiv_rows:
        title_key = normalize_title(row["title"])
        has_doi = bool(row["doi"]) and row["doi"] in openalex_dois
        if title_key in openalex_titles or has_doi:
            continue
        missed.append(row)

    return {
        "topic": topic_id,
        "total": total,
        "venue_coverage": round(venue_hits / total, 4),
        "referenced_works_completeness": round(ref_complete / total, 4),
        "oa_availability": round(oa_available / total, 4),
        "arxiv_total": len(arxiv_rows),
        "arxiv_missing_from_openalex": len(missed),
        "arxiv_gap_rate": round(len(missed) / len(arxiv_rows), 4) if arxiv_rows else None,
        "arxiv_missed_examples": [row["title"][:90] for row in missed[:5]],
        "no_venue_share": round(sum(1 for row in rows if not row["venue"]) / total, 4),
        "no_references_share": round((total - ref_complete) / total, 4),
    }


def spot_check(rows: list[dict[str, Any]], *, sample_size: int = 10) -> dict[str, Any]:
    """自动核验 10 篇元数据（供人工二次核对）。"""
    if not rows:
        return {"checked": 0, "passed": 0, "samples": []}
    step = max(1, len(rows) // sample_size)
    samples = rows[::step][:sample_size]
    passed = 0
    details: list[dict[str, Any]] = []
    current_year = datetime.now(UTC).year
    for row in samples:
        checks = {
            "title_ok": len(row["title"].strip()) > 10,
            "year_ok": bool(row["year"]) and 1800 < int(row["year"]) <= current_year + 1,
            "identifier_ok": bool(row["paper_id"] or row["doi"]),
            "authors_ok": int(row["authors_count"]) >= 1,
        }
        ok = all(checks.values())
        passed += int(ok)
        details.append(
            {"title": row["title"][:80], "year": row["year"], "venue": row["venue"][:40], **checks}
        )
    return {
        "checked": len(samples),
        "passed": passed,
        "pass_rate": round(passed / len(samples), 4),
        "samples": details,
    }


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Spike S1：数据源覆盖度验证")
    parser.add_argument("--topics", default="T1,T2", help="要验证的 topic（默认 T1,T2）")
    parser.add_argument("--years", type=int, default=3, help="往回追溯的年数（默认 3）")
    parser.add_argument("--limit", type=int, default=200, help="每源每查询的条数上限（默认 200）")
    parser.add_argument("--out", default="out/s1_coverage.csv", help="明细 CSV 路径")
    parser.add_argument("--summary", default="out/s1_coverage.json", help="汇总 JSON 路径")
    parser.add_argument("--skip-probe", action="store_true", help="跳过限速探测")
    parser.add_argument(
        "--venue-sufficiency", action="store_true", help="附加：白名单 venue 过滤后的召回量"
    )
    parser.add_argument(
        "--arxiv-existence",
        type=int,
        default=0,
        metavar="N",
        help="附加：抽样 N 篇 arXiv 论文检查是否收录于 OpenAlex（0=关闭）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    setup_logging(settings)
    run_id = f"p0-s1-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    log = open_event_log(settings.paths.out_dir / "events.jsonl", run_id=run_id)
    clear_context()
    bind_context(run_id=run_id, stage="S1_source_coverage", agent="single")

    since_year = datetime.now(UTC).year - args.years
    mailto = settings.sources.openalex_mailto
    topic_ids = [item.strip() for item in args.topics.split(",") if item.strip()]

    log_event(
        Severity.INFO,
        "spike_started",
        "S1 源覆盖度验证开始",
        topics=topic_ids,
        since_year=since_year,
        limit=args.limit,
        mailto_domain=mailto.split("@")[-1],
    )
    log.emit(
        EventType.PHASE_CHANGE,
        payload={"spike": "S1", "topics": topic_ids, "since_year": since_year},
    )

    all_rows: list[dict[str, Any]] = []
    all_arxiv_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for topic_id in topic_ids:
        topic = TOPICS.get(topic_id)
        if topic is None:
            log_event(Severity.WARNING, "topic_unknown", "未知 topic，跳过", topic=topic_id)
            continue

        openalex_rows: list[dict[str, Any]] = []
        for query in topic["openalex_queries"]:
            try:
                records = fetch_openalex(
                    query, since_year=since_year, limit=args.limit, mailto=mailto
                )
                openalex_rows.extend(openalex_to_row(item, topic_id) for item in records)
            except Exception as exc:  # noqa: BLE001 - 单个查询失败不终止整个 spike
                log_event(
                    Severity.ERROR,
                    "source_call_failed",
                    "OpenAlex 查询失败",
                    source="openalex",
                    query=query,
                    error_code="E_SRC_TIMEOUT"
                    if isinstance(exc, httpx.TimeoutException)
                    else "E_SRC_5XX",
                    error=str(exc)[:200],
                )
                log.emit(
                    EventType.ERROR,
                    severity=Severity.ERROR,
                    payload={"error_code": "E_SRC_REQUEST_FAILED", "query": query},
                )

        try:
            arxiv_records = fetch_arxiv(
                topic["arxiv_query"], since_year=since_year, limit=args.limit
            )
            arxiv_rows = [arxiv_to_row(item, topic_id) for item in arxiv_records]
        except Exception as exc:  # noqa: BLE001
            log_event(
                Severity.ERROR,
                "source_call_failed",
                "arXiv 查询失败",
                source="arxiv",
                error_code="E_SRC_REQUEST_FAILED",
                error=str(exc)[:200],
            )
            arxiv_rows = []

        all_arxiv_rows.extend(arxiv_rows)
        summary = summarize_topic(topic_id, openalex_rows, arxiv_rows)
        summaries.append(summary)
        all_rows.extend(openalex_rows)

        log_event(
            Severity.INFO,
            "topic_coverage_computed",
            "覆盖度指标计算完成",
            topic=topic_id,
            venue_coverage=summary.get("venue_coverage"),
            references_completeness=summary.get("referenced_works_completeness"),
            oa_availability=summary.get("oa_availability"),
            arxiv_gap_rate=summary.get("arxiv_gap_rate"),
        )
        log.emit(
            EventType.METRIC,
            payload={
                "topic": topic_id,
                "venue_coverage": summary.get("venue_coverage"),
                "oa_availability": summary.get("oa_availability"),
                "arxiv_gap_rate": summary.get("arxiv_gap_rate"),
            },
        )

    checks = spot_check(all_rows)
    probe = {} if args.skip_probe else rate_limit_probe(mailto)
    if probe:
        log.emit(EventType.METRIC, payload={"rate_probe": probe})

    sufficiency: dict[str, Any] = {}
    if args.venue_sufficiency:
        source_ids = resolve_venue_source_ids(mailto)
        sufficiency = venue_sufficiency(
            [topic["name"] for topic in (TOPICS[t] for t in topic_ids if t in TOPICS)],
            list(source_ids),
            since_year=since_year,
            mailto=mailto,
        )
        sufficiency["venue_names"] = list(source_ids.values())
        log_event(
            Severity.INFO,
            "venue_sufficiency_computed",
            "白名单 venue 召回量计算完成",
            venues=len(source_ids),
            total=sufficiency.get("total_matched"),
            per_year=sufficiency.get("per_year_estimate"),
        )
        log.emit(EventType.METRIC, payload={"venue_sufficiency": sufficiency.get("total_matched")})

    existence: dict[str, Any] = {}
    if args.arxiv_existence > 0:
        existence = openalex_existence_probe(
            all_arxiv_rows, mailto=mailto, sample_size=args.arxiv_existence
        )
        log_event(
            Severity.INFO,
            "arxiv_existence_computed",
            "arXiv 论文 OpenAlex 收录率计算完成",
            sampled=existence.get("sampled"),
            found_rate=existence.get("found_rate"),
        )
        log.emit(EventType.METRIC, payload={"arxiv_found_rate": existence.get("found_rate")})

    out_csv = settings.paths.out_dir.parent / args.out
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(all_rows[0].keys()) if all_rows else ["topic"]
        )
        writer.writeheader()
        writer.writerows(all_rows)

    payload = {
        "run_id": run_id,
        "generated_at": datetime.now(UTC).isoformat(),
        "since_year": since_year,
        "limit": args.limit,
        "mailto": mailto,
        "topics": summaries,
        "spot_check": checks,
        "rate_probe": probe,
        "venue_sufficiency": sufficiency,
        "arxiv_existence": existence,
    }
    out_summary = settings.paths.out_dir.parent / args.summary
    out_summary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"run_id  {run_id}")
    print(f"csv     {out_csv}")
    print(f"summary {out_summary}")
    for summary in summaries:
        print(
            "topic {topic}: n={total} venue_cov={venue_coverage} refs={referenced_works_completeness} "
            "oa={oa_availability} arxiv_gap={arxiv_gap_rate}".format(**summary)
        )
    print(
        f"spot_check {checks['passed']}/{checks['checked']} passed (pass_rate={checks['pass_rate']})"
    )
    if probe:
        print(f"rate_probe {probe}")
    if sufficiency:
        print(
            "venue_sufficiency "
            f"venues={sufficiency.get('venues_resolved')} "
            f"total={sufficiency.get('total_matched')} "
            f"per_year≈{sufficiency.get('per_year_estimate')}"
        )
    if existence:
        print(
            "arxiv_in_openalex "
            f"{existence.get('found')}/{existence.get('sampled')} "
            f"(found_rate={existence.get('found_rate')})"
        )
    log_event(
        Severity.INFO,
        "spike_finished",
        "S1 完成",
        topics=len(summaries),
        rows=len(all_rows),
        spot_check_pass_rate=checks["pass_rate"],
    )
    clear_context()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

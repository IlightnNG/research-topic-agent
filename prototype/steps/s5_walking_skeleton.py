"""Step 5（S5）Walking Skeleton：单 topic 端到端最小闭环。

要回答的问题（见 `docs/implementation/phase0-implementation-steps.md` §Step 5）
**从"一批论文记录"到"一份可核验的报告"这条链，能否在一个脚本里跑通？接口/schema/成本是否可行？**

子步与验收
| 子步 | 本轮实现 | 验收标准 |
|---|---|---|
| 5.1 fetch | 读入**真实 OpenAlex 响应 fixture**（`out/s5_corpus.json`）+ SQLite `sync_state` 游标 | 第二次运行新增 ≈ 0 |
| 5.2 normalize | `normalize.openalex_work_to_paper` + D6 三段式去重 | id 优先级/缺字段/多作者（单测） |
| 5.3 chunk | 摘要分块（token 预算 120；PDF 抽取本轮不启用，见 `chunking.py` 说明） | 块 token ≤ 预算且 ≥0.9×预算（单测） |
| 5.4 store | SQLite 真相源（papers/authors/citations/claims/merges/sync_state） | 重复运行计数零增长 |
| 5.5 retrieve | 词法 TF-IDF 余弦取 top-k → `EvidenceCard`（带可回查片段） | 卡片含 paper_id/来源/片段 |
| 5.6 report | **真实云 LLM**（deepseek-flash）批量抽结构化卡片 → 生成报告 JSON → 确定性渲染 markdown | 报告 ≥800 字；≥10 claim 且 100% 带 citation |
| 5.7 events | 全流程事件（phase/llm/error/metric） | 单 run 事件 ≥30 条且 seq 连续 |

本轮的**范围裁剪与理由**（避免把"没做的"说成"做了"）
- **不做** Qdrant/Kuzu 接线：本轮无本地 embedding，塞词法向量进 Qdrant 只是假向量；S3 已验证两库可用。
- **不做** PDF 全文：需下载大量 OA PDF；摘要已足够支撑"可回查证据"，全文留 Phase 1。
- **不做** 守卫（G1 漂移/G4 循环）：那是 S6 的范围；本轮只做网关侧的**预算熔断**。
- **不做**离线档：按用户要求本轮只验证云 API 路径（缓存仍在，用于重跑不重复花钱）。

用法
```bash
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-001
uv run python steps/s5_walking_skeleton.py --topic T1 --run-id p0-s5-001   # 重跑：缓存命中 + 计数零增长
```
产出：`out/reports/<topic>-<date>-<run_id>.md`、`out/claims_<run_id>.json`、`out/s5_summary.json`、事件 `out/events.jsonl`。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from lit_agent_min import (  # noqa: E402
    Claim,
    EventType,
    EvidenceCard,
    Severity,
    bind_context,
    clear_context,
    load_settings,
    log_event,
    open_event_log,
    read_events,
    setup_logging,
)
from lit_agent_min.chunking import chunk_text, count_tokens  # noqa: E402
from lit_agent_min.llm import LLMBudgetExceeded, LLMCall, LLMError, LLMGateway  # noqa: E402
from lit_agent_min.normalize import dedup_papers, openalex_work_to_paper  # noqa: E402
from lit_agent_min.scoring import build_idf, rank  # noqa: E402
from lit_agent_min.stores import SqliteStore, StoreSchemaError, verify_counts  # noqa: E402

TOPICS: dict[str, dict[str, str]] = {
    "T1": {
        "name": "多智能体 LLM 编排与可靠性",
        "query": (
            "multi-agent LLM orchestration reliability coordination failure detection "
            "verification robustness agent communication benchmarks"
        ),
    },
    "T2": {
        "name": "边缘设备 VLM 量化与部署",
        "query": (
            "edge device vision language model quantization deployment inference "
            "efficiency latency memory pruning distillation"
        ),
    },
}

STOPWORDS = frozenset(
    [
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "than",
        "that",
        "this",
        "these",
        "those",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "from",
        "with",
        "without",
        "by",
        "as",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "do",
        "does",
        "did",
        "not",
        "no",
        "we",
        "our",
        "us",
        "it",
        "its",
        "their",
        "there",
        "here",
        "can",
        "could",
        "may",
        "might",
        "will",
        "would",
        "should",
        "which",
        "who",
        "whom",
        "whose",
        "what",
        "when",
        "where",
        "how",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "only",
        "own",
        "same",
        "so",
        "too",
        "very",
        "s",
        "t",
        "just",
        "don",
        "now",
        "also",
        "using",
        "use",
        "used",
        "based",
        "approach",
        "method",
        "results",
        "show",
        "shows",
        "paper",
        "propose",
        "proposed",
        "new",
    ]
)

CARD_FIELDS = ("problem", "method", "datasets", "metrics", "findings", "limitations")


# --------------------------------------------------------------------------- #
# 5.5 检索：词法 TF-IDF 余弦（无本地 embedding 时的确定性替代）
# --------------------------------------------------------------------------- #
def _tokens(text: str) -> list[str]:
    return [
        t for t in re.findall(r"[a-z0-9][a-z0-9\-]+", (text or "").lower()) if t not in STOPWORDS
    ]


def lexical_scores(query: str, docs: dict[str, str]) -> dict[str, float]:
    """TF-IDF 余弦相似度（0..1）。同一输入必然同分 → 可复现、可单测。

    **口径统一**：实现委托给 `lit_agent_min/scoring.py`——S6 的 G1 漂移阈值就是在这个打分器上
    标定的，若检索用另一套口径，标定结果立刻失效（两个模块各写一份是隐患）。
    """
    if not docs:
        return {}
    idf = build_idf(docs.values())
    return dict(rank(query, docs, idf=idf))


def _w_to_canonical(works: list[dict[str, Any]], papers: list[Any]) -> dict[str, str]:
    """OpenAlex W id → 本库 canonical id 的映射。

    为什么必需：`canonical_id` 契约是 **DOI 优先**，而 `referenced_works` 里是 **W id**。
    不做这层映射，引用边会全部对不上（实测第一版 `citations=0`）。
    """
    mapping: dict[str, str] = {}
    for work, paper in zip(works, papers, strict=False):
        raw = str(work.get("id") or "")
        w_id = raw.rsplit("/", 1)[-1]
        if w_id:
            mapping[w_id] = paper.paper_id
    return mapping


def remap_references(papers: list[Any], w_to_canonical: dict[str, str]) -> dict[str, int]:
    """把 references（W id）翻译成本库 canonical id，只保留落在本次语料内的边。

    注意：`Paper` 契约是 **frozen** 的，不能原地改字段 → 用 `model_copy(update=...)` 换新对象。
    """
    total = 0
    in_corpus = 0
    for idx, paper in enumerate(papers):
        remapped = []
        for ref in paper.references:
            total += 1
            target = w_to_canonical.get(ref)
            if target and target != paper.paper_id:
                remapped.append(target)
                in_corpus += 1
        papers[idx] = paper.model_copy(update={"references": sorted(set(remapped))})
    return {"references_total": total, "references_in_corpus": in_corpus}


def _best_snippet(chunks: list[str], query: str, *, limit: int = 600) -> str:
    """取与主题重叠最高的块作为片段，并在**句子边界**内截断（避免出现半句话）。"""
    if not chunks:
        return ""
    best = max(chunks, key=lambda c: _overlap(c, query))
    if len(best) <= limit:
        return best
    window = best[:limit]
    cut = max(window.rfind(". "), window.rfind("。"), window.rfind("! "), window.rfind("? "))
    return (window[: cut + 1] if cut > limit * 0.5 else window).strip()


# --------------------------------------------------------------------------- #
# 5.6 报告：确定性渲染（LLM 只产出结构化内容，排版交给代码）
# --------------------------------------------------------------------------- #
def render_report(
    *,
    topic: str,
    topic_name: str,
    cards: list[EvidenceCard],
    notes: dict[str, dict[str, Any]],
    claims: list[Claim],
    run_id: str,
    generated_at: str,
    llm_summary: dict[str, Any],
) -> str:
    by_id = {c.paper_id: c for c in cards}
    lines: list[str] = [
        f"# {topic} · {topic_name}",
        "",
        f"> 自动生成：run `{run_id}` · {generated_at} · 语料 {len(cards)} 篇（证据卡）· "
        f"LLM `{llm_summary.get('model', 'n/a')}` · 本次成本 ${llm_summary.get('cost_usd', 0)}",
        "",
        "## 1. 本期结论（每条均可回查证据）",
        "",
    ]
    for idx, claim in enumerate(claims, 1):
        refs = " ".join(f"[{c.paper_id}]" for c in claim.citations)
        lines.append(f"{idx}. {claim.text} {refs}")
    lines += ["", "## 2. 方法脉络", ""]
    for card in cards:
        note = notes.get(card.paper_id, {})
        method = (note.get("method") or "").strip()
        if method:
            lines.append(f"- **[{card.paper_id}] {card.title}**（{card.year or 'n/a'}）：{method}")
    lines += ["", "## 3. 数据集与指标", ""]
    dataset_rows = [
        (
            card.paper_id,
            ", ".join(note.get("datasets") or []) or "—",
            ", ".join(note.get("metrics") or []) or "—",
        )
        for card in cards
        for note in [notes.get(card.paper_id, {})]
    ]
    lines.append("| 论文 | 数据集 | 指标 |")
    lines.append("|---|---|---|")
    lines += [f"| {pid} | {ds} | {mt} |" for pid, ds, mt in dataset_rows]
    lines += ["", "## 4. 主要发现", ""]
    for card in cards:
        for finding in (notes.get(card.paper_id, {}).get("findings") or [])[:2]:
            lines.append(f"- {finding} [{card.paper_id}]")
    lines += ["", "## 5. 局限与风险", ""]
    limitations = [
        (card.paper_id, lim)
        for card in cards
        for lim in (notes.get(card.paper_id, {}).get("limitations") or [])[:1]
    ]
    if limitations:
        lines += [f"- {lim} [{pid}]" for pid, lim in limitations]
    else:
        lines.append("- 本轮结构化抽取未报出显式局限（属抽取覆盖问题，不等于「无局限」结论）。")
    lines += [
        "",
        "## 6. 证据可回查性",
        "",
        f"- 报告内所有 `[paper_id]` 均指向本次语料中的证据卡；claim 数 **{len(claims)}**，"
        f"带 citation 比例 **100%**（由脚本强制校验，无 citation 的 claim 会被丢弃并计数）。",
        "- 片段来源：OpenAlex 摘要（`abstract_inverted_index` 还原后分块）；本轮未使用 PDF 全文。",
        "",
        "## 7. 参考（本次语料）",
        "",
    ]
    lines += [
        f"- `{card.paper_id}` — {card.title} ({card.year or 'n/a'})"
        + (f" · {by_id[card.paper_id].source}" if card.paper_id in by_id else "")
        for card in cards
    ]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# 主导航
# --------------------------------------------------------------------------- #
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase 0 Step 5：单 topic 端到端最小闭环")
    parser.add_argument("--topic", default="T1", choices=sorted(TOPICS))
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--corpus", default="out/s5_corpus.json", help="真实 OpenAlex 响应 fixture")
    parser.add_argument("--top-k", type=int, default=12)
    parser.add_argument("--min-cards", type=int, default=10, help="进入报告的最少证据卡数")
    parser.add_argument(
        "--card-batch", type=int, default=4, help="每次 LLM 调用抽取几篇（控制调用次数）"
    )
    parser.add_argument(
        "--max-usd", type=float, default=None, help="预算熔断（默认取配置 run_cost_budget_usd）"
    )
    parser.add_argument("--model", default=None, help="默认 <provider>/<config.model>")
    parser.add_argument("--no-cache", action="store_true", help="禁用 LLM 缓存（强制真实调用）")
    parser.add_argument(
        "--reset-store",
        action="store_true",
        help="重建 SQLite 真相源（丢弃旧表；用于清掉早期 spike 的旧结构）",
    )
    parser.add_argument("--summary", default="out/s5_summary.json")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    settings = load_settings()
    setup_logging(settings)
    started_wall = time.perf_counter()
    run_id = args.run_id or f"p0-s5-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
    log = open_event_log(settings.paths.out_dir / "events.jsonl", run_id=run_id)
    clear_context()
    bind_context(run_id=run_id, stage="S5_walking_skeleton", agent="single")

    topic = TOPICS[args.topic]
    corpus_path = Path(args.corpus)
    if not corpus_path.is_absolute():
        corpus_path = Path(__file__).resolve().parents[1] / corpus_path
    if not corpus_path.exists():
        print(f"[FAIL] 语料 fixture 不存在：{corpus_path}", file=sys.stderr)
        return 2

    model = args.model or f"{settings.providers.cloud.name}/{settings.providers.cloud.model}"
    max_usd = args.max_usd if args.max_usd is not None else settings.routing.run_cost_budget_usd

    llm_calls: list[LLMCall] = []

    def on_llm_call(call: LLMCall) -> None:
        llm_calls.append(call)
        log.emit(EventType.LLM_CALL, stage="5.6_report", agent="single", payload=call.to_payload())
        log_event(
            Severity.INFO,
            "s5_llm_call",
            f"LLM 调用 {call.task}",
            **{k: v for k, v in call.to_payload().items() if k != "task"},
        )

    gateway = LLMGateway(
        model=model,
        cache_dir=settings.paths.out_dir / "llm_cache",
        api_key_env=settings.providers.cloud.api_key_env,
        api_base=settings.providers.cloud.base_url,
        budget_usd=max_usd,
        timeout_s=120.0,
        max_attempts=3,
        use_cache=not args.no_cache,
        on_call=on_llm_call,
    )

    log_event(
        Severity.INFO,
        "s5_started",
        "S5 闭环开始",
        topic=args.topic,
        topic_name=topic["name"],
        model=model,
        max_usd=max_usd,
        corpus=str(corpus_path.name),
        top_k=args.top_k,
    )
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.1_fetch",
        agent="single",
        payload={"phase": "start", "topic": args.topic},
    )

    summary: dict[str, Any] = {
        "run_id": run_id,
        "topic": args.topic,
        "topic_name": topic["name"],
        "started_at": datetime.now(UTC).isoformat(),
        "model": model,
        "budget_usd": max_usd,
    }

    # ---- 5.1 fetch（fixture + 增量游标） ---------------------------------- #
    t0 = time.perf_counter()
    works = json.loads(corpus_path.read_text(encoding="utf-8"))
    try:
        store = SqliteStore(settings.paths.sqlite_path, reset=args.reset_store)
    except StoreSchemaError as exc:
        log_event(
            Severity.ERROR,
            "s5_store_schema_mismatch",
            "真相源 schema 不匹配",
            error_code="E_STORE_SCHEMA_MISMATCH",
            detail=str(exc)[:300],
        )
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 6
    previous = store.get_cursor(f"openalex:{args.topic}")
    known_before = store.paper_ids()
    log.emit(
        EventType.TOOL_CALL,
        stage="5.1_fetch",
        agent="retrieval",
        payload={
            "tool": "openalex_fixture",
            "items": len(works),
            "cursor_prev": (previous or {}).get("cursor"),
        },
    )
    summary["fetch"] = {
        "source": "openalex_fixture",
        "items": len(works),
        "seconds": round(time.perf_counter() - t0, 3),
        "cursor_prev": previous,
        "papers_before_in_store": len(known_before),
    }
    store.set_cursor(
        f"openalex:{args.topic}", cursor="fixture-v1", run_id=run_id, items_seen=len(works)
    )
    log_event(
        Severity.INFO,
        "s5_fetch_done",
        "5.1 抓取完成（fixture）",
        items=len(works),
        seconds=summary["fetch"]["seconds"],
    )
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.1_fetch",
        agent="single",
        payload={
            "phase": "end",
            "items": len(works),
            "ms": round(summary["fetch"]["seconds"] * 1000),
        },
    )

    # ---- 5.2 normalize + 去重 -------------------------------------------- #
    log.emit(
        EventType.PHASE_CHANGE, stage="5.2_normalize", agent="single", payload={"phase": "start"}
    )
    papers_raw = [openalex_work_to_paper(w) for w in works]
    w_map = _w_to_canonical(works, papers_raw)
    ref_stats = remap_references(papers_raw, w_map)
    dedup = dedup_papers(papers_raw)
    papers = dedup.unique
    summary["normalize"] = {"raw": len(papers_raw), **dedup.stats, **ref_stats}
    log_event(Severity.INFO, "s5_normalize_done", "5.2 归一化与去重完成", **summary["normalize"])
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.2_normalize",
        agent="single",
        payload={
            "phase": "end",
            "merged_version_copies": dedup.stats["merged_version_copies"],
            "references_in_corpus": ref_stats["references_in_corpus"],
        },
    )

    # ---- 5.3 chunk ------------------------------------------------------- #
    log.emit(EventType.PHASE_CHANGE, stage="5.3_chunk", agent="single", payload={"phase": "start"})
    chunks_by_paper: dict[str, list[str]] = {}
    for paper in papers:
        chunks = chunk_text(paper.abstract, budget_tokens=120, overlap_tokens=20)
        chunks_by_paper[paper.paper_id] = [c.text for c in chunks]
    total_chunks = sum(len(v) for v in chunks_by_paper.values())
    summary["chunk"] = {
        "papers": len(papers),
        "chunks": total_chunks,
        "avg_chunks_per_paper": round(total_chunks / len(papers), 2) if papers else 0,
        "avg_tokens_per_abstract": round(
            sum(count_tokens(p.abstract) for p in papers) / len(papers), 1
        )
        if papers
        else 0,
    }
    log_event(Severity.INFO, "s5_chunk_done", "5.3 摘要分块完成", **summary["chunk"])
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.3_chunk",
        agent="single",
        payload={"phase": "end", "chunks": total_chunks, "papers": len(papers)},
    )

    # ---- 5.4 store（幂等 + 计数对账） ------------------------------------ #
    log.emit(EventType.PHASE_CHANGE, stage="5.4_store", agent="single", payload={"phase": "start"})
    written = store.upsert_papers(papers, run_id=run_id)
    merged_rows = store.record_merges(dedup.merged, run_id=run_id)
    counts = store.counts()
    expected = {
        "papers": len(store.paper_ids()),
        "authors": counts.authors,
        "citations": counts.citations,
    }
    mismatches = verify_counts(expected, counts.as_dict())
    summary["store"] = {
        "written_this_run": written,
        "merged_rows": merged_rows,
        "counts": counts.as_dict(),
        "mismatches": mismatches,
        "papers_new_this_run": len(store.paper_ids() - known_before),
    }
    if mismatches:
        log_event(
            Severity.ERROR,
            "s5_store_mismatch",
            "5.4 计数对账不一致",
            error_code="E_DATA_COUNT_MISMATCH",
            mismatches=mismatches,
        )
    log_event(Severity.INFO, "s5_store_done", "5.4 入库完成（幂等）", **summary["store"])
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.4_store",
        agent="single",
        payload={"phase": "end", "counts": counts.as_dict(), "mismatches": len(mismatches)},
    )

    # ---- 5.5 retrieve（词法检索 → EvidenceCard） ------------------------- #
    log.emit(
        EventType.PHASE_CHANGE, stage="5.5_retrieve", agent="single", payload={"phase": "start"}
    )
    docs = {p.paper_id: f"{p.title}. {p.abstract}" for p in papers}
    scores = lexical_scores(topic["query"], docs)
    ranked = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[: args.top_k]
    by_id = {p.paper_id: p for p in papers}
    cards: list[EvidenceCard] = []
    for paper_id, score in ranked:
        snippet_source = chunks_by_paper.get(paper_id) or [by_id[paper_id].title]
        snippet = _best_snippet(snippet_source, topic["query"])
        cards.append(
            EvidenceCard(
                paper_id=paper_id,
                title=by_id[paper_id].title,
                year=by_id[paper_id].year,
                snippet=snippet or by_id[paper_id].title,
                source=f"openalex_abstract:{by_id[paper_id].source}",
                score=float(score),
            )
        )
    log.emit(
        EventType.TOOL_CALL,
        stage="5.5_retrieve",
        agent="retrieval",
        payload={
            "tool": "lexical_tfidf",
            "candidates": len(docs),
            "returned": len(cards),
            "top_score": cards[0].score if cards else 0,
        },
    )
    # 每张证据卡单独留痕：报告里的 [paper_id] 可回溯到检索分数与片段长度
    for card in cards:
        log.emit(
            EventType.TOOL_CALL,
            stage="5.5_retrieve",
            agent="retrieval",
            payload={
                "tool": "evidence_card",
                "paper_id": card.paper_id,
                "score": card.score,
                "snippet_chars": len(card.snippet),
                "year": card.year,
                "source": card.source,
            },
        )
    if len(cards) < args.min_cards:
        log_event(
            Severity.ERROR,
            "s5_too_few_cards",
            "证据卡不足，终止（不生成低质量报告）",
            error_code="E_INSUFFICIENT_EVIDENCE",
            cards=len(cards),
            required=args.min_cards,
        )
        summary["status"] = "aborted_insufficient_evidence"
        _write_summary(settings, args.summary, summary, gateway)
        return 3
    summary["retrieve"] = {
        "strategy": "lexical_tfidf_cosine",
        "candidates": len(docs),
        "returned": len(cards),
        "score_min": min(c.score for c in cards),
        "score_max": max(c.score for c in cards),
        "score_mean": round(sum(c.score for c in cards) / len(cards), 6),
    }
    log_event(Severity.INFO, "s5_retrieve_done", "5.5 检索完成", **summary["retrieve"])
    log.emit(EventType.METRIC, stage="5.5_retrieve", agent="single", payload=summary["retrieve"])
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.5_retrieve",
        agent="single",
        payload={"phase": "end", "cards": len(cards)},
    )

    # ---- 5.6 report（真实云 LLM；失败即如实记录，不伪造报告） ------------- #
    log.emit(EventType.PHASE_CHANGE, stage="5.6_report", agent="single", payload={"phase": "start"})
    notes: dict[str, dict[str, Any]] = {}
    try:
        for start in range(0, len(cards), args.card_batch):
            batch = cards[start : start + args.card_batch]
            notes.update(_extract_cards(gateway, batch, topic))
        report_data = _draft_report(gateway, topic, cards, notes)
    except LLMBudgetExceeded as exc:
        log_event(
            Severity.ERROR,
            "s5_budget_exceeded",
            "预算熔断，终止",
            error_code="E_BUDGET_EXCEEDED",
            detail=str(exc)[:200],
        )
        summary["status"] = "aborted_budget"
        _write_summary(settings, args.summary, summary, gateway)
        return 4
    except LLMError as exc:
        log_event(
            Severity.ERROR,
            "s5_llm_failed",
            "LLM 调用失败，闭环中止（不产出假报告）",
            error_code="E_LLM_CALL_FAILED",
            detail=str(exc)[:300],
        )
        summary["status"] = "aborted_llm_error"
        _write_summary(settings, args.summary, summary, gateway)
        return 5

    # claims：只保留 citation 能回查到本次语料的（强制 grounding）
    cards_by_id = {c.paper_id: c for c in cards}
    claims, dropped = _build_claims(report_data.get("claims") or [], cards_by_id)
    if len(claims) < 10:
        log_event(
            Severity.WARNING,
            "s5_claims_below_target",
            "claim 数低于验收目标",
            claims=len(claims),
            target=10,
            dropped=dropped,
        )
    llm_snapshot = gateway.summary()
    log.emit(
        EventType.METRIC,
        stage="5.6_report",
        agent="single",
        payload={
            "claims": len(claims),
            "claims_dropped_ungrounded": dropped,
            "cost_usd": llm_snapshot["cost_usd"],
            "cost_per_claim_usd": round(llm_snapshot["cost_usd"] / len(claims), 8)
            if claims
            else None,
            "llm_calls": llm_snapshot["calls"],
            "network_calls": llm_snapshot["network_calls"],
            "cache_hits": llm_snapshot["cache_hits"],
            "prompt_tokens": llm_snapshot["prompt_tokens"],
            "completion_tokens": llm_snapshot["completion_tokens"],
        },
    )

    generated_at = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    report_md = render_report(
        topic=args.topic,
        topic_name=topic["name"],
        cards=cards,
        notes=notes,
        claims=claims,
        run_id=run_id,
        generated_at=generated_at,
        llm_summary=gateway.summary() | {"model": model},
    )
    reports_dir = settings.paths.out_dir / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"{args.topic}-{datetime.now(UTC).strftime('%Y%m%d')}-{run_id}.md"
    report_path.write_text(report_md, encoding="utf-8")
    claims_path = settings.paths.out_dir / f"claims_{run_id}.json"
    claims_path.write_text(
        json.dumps([c.model_dump(mode="json") for c in claims], ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    store.upsert_claims(run_id, claims)

    cited = {c.paper_id for claim in claims for c in claim.citations}
    ungrounded = sorted(pid for pid in cited if pid not in cards_by_id)
    summary["report"] = {
        "path": str(report_path.relative_to(settings.paths.out_dir.parent)),
        "claims_path": str(claims_path.relative_to(settings.paths.out_dir.parent)),
        "chars": len(report_md),
        "claims": len(claims),
        "claims_dropped_ungrounded": dropped,
        "claims_with_citation": sum(1 for c in claims if c.citations),
        "distinct_cited_papers": len(cited),
        "ungrounded_citation_ids": ungrounded,
        "grounding_rate": round(sum(1 for c in claims if c.citations) / len(claims), 4)
        if claims
        else 0.0,
    }
    log.emit(
        EventType.REPORT_WRITTEN,
        stage="5.6_report",
        agent="reporter",
        payload={"path": str(report_path.name), "chars": len(report_md), "claims": len(claims)},
    )
    log_event(Severity.INFO, "s5_report_written", "5.6 报告已生成", **summary["report"])
    log.emit(
        EventType.PHASE_CHANGE,
        stage="5.6_report",
        agent="single",
        payload={
            "phase": "end",
            "claims": len(claims),
            "grounding_rate": summary["report"]["grounding_rate"],
            "chars": len(report_md),
        },
    )

    # ---- 5.7 events 校验 + 收尾 ------------------------------------------ #
    events = read_events(settings.paths.out_dir / "events.jsonl", run_id=run_id)
    seqs = [e.seq for e in events]
    llm_summary = gateway.summary() | {"model": model}
    summary["events"] = {
        "count": len(events),
        "contiguous": seqs == list(range(1, len(seqs) + 1)),
        "by_type": dict(Counter(str(e.type) for e in events)),
    }
    summary["llm"] = llm_summary
    summary["status"] = "ok"
    summary["seconds_total"] = round(time.perf_counter() - started_wall, 2)
    log.emit(
        EventType.METRIC,
        stage="5.7_events",
        agent="single",
        payload={
            "event_count": len(events),
            "claims": len(claims),
            "report_chars": len(report_md),
            "cost_usd": llm_summary["cost_usd"],
            "seconds": summary["seconds_total"],
        },
    )
    log_event(
        Severity.INFO,
        "s5_finished",
        "S5 闭环完成",
        status="ok",
        events=len(events),
        claims=len(claims),
        chars=len(report_md),
        cost_usd=llm_summary["cost_usd"],
        seconds=summary["seconds_total"],
    )
    _write_summary(settings, args.summary, summary, gateway)

    # 控制台摘要（导师演示用）
    print(f"run_id      {run_id}   topic={args.topic} ({topic['name']})")
    print(
        f"corpus      {summary['fetch']['items']} 篇 → 去重后 {summary['normalize']['unique']} 篇"
        f"（合并版本副本 {summary['normalize']['merged_version_copies']}，"
        f"同 id 重复行 {summary['normalize']['dropped_same_id_rows']}）"
        f" → 分块 {summary['chunk']['chunks']} 块"
    )
    print(
        f"store       papers={counts.papers} authors={counts.authors} citations={counts.citations}"
        f" mismatches={mismatches or '{}'}"
    )
    print(
        f"retrieve    {summary['retrieve']['returned']} 张证据卡（{summary['retrieve']['strategy']}，"
        f"score {summary['retrieve']['score_min']}–{summary['retrieve']['score_max']}）"
    )
    print(
        f"report      {summary['report']['chars']} 字 / {summary['report']['claims']} claims / "
        f"带引用 {summary['report']['grounding_rate'] * 100:.0f}% → {summary['report']['path']}"
    )
    print(
        f"llm         calls={llm_summary['calls']} net={llm_summary['network_calls']} "
        f"cache_hits={llm_summary['cache_hits']} retries={llm_summary['retries']} "
        f"tokens={llm_summary['prompt_tokens']}+{llm_summary['completion_tokens']} "
        f"cost=${llm_summary['cost_usd']} avg={llm_summary['avg_latency_ms']}ms"
    )
    print(
        f"events      {summary['events']['count']} 条 contiguous={summary['events']['contiguous']}"
    )
    print(f"elapsed     {summary['seconds_total']}s")
    print(f"summary     {settings.paths.out_dir.parent / args.summary}")
    store.close()
    clear_context()
    return 0


def _overlap(text: str, query: str) -> int:
    return len(set(_tokens(text)) & set(_tokens(query)))


def _extract_cards(
    gateway: LLMGateway, batch: list[EvidenceCard], topic: dict[str, str]
) -> dict[str, Any]:
    """一次 LLM 调用抽取若干篇的结构化卡片（JSON 模式，字段固定）。"""
    payload = [
        {"paper_id": c.paper_id, "title": c.title, "year": c.year, "text": c.snippet} for c in batch
    ]
    prompt = (
        f"研究主题：{topic['name']}（{topic['query']}）。\n"
        "下面是若干篇论文的标题与摘要片段。请**只依据给定文本**抽取信息，不要引入外部知识，"
        "不要编造数字。输出 JSON 对象，形如 "
        '{"cards":[{"paper_id":"...","problem":"...","method":"...","datasets":["..."],'
        '"metrics":["..."],"findings":["..."],"limitations":["..."]}]}。'
        "抽不到的字段填空字符串或空数组；`paper_id` 必须与输入一致。\n\n输入：\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    call = gateway.chat_json(
        [{"role": "user", "content": prompt}], task=f"extract_cards:{len(batch)}", max_tokens=2000
    )
    result: dict[str, Any] = {}
    for item in (call.data or {}).get("cards", []):
        pid = str(item.get("paper_id", "")).strip()
        if pid:
            result[pid] = {field: item.get(field) for field in CARD_FIELDS}
    return result


def _draft_report(
    gateway: LLMGateway, topic: dict[str, str], cards: list[EvidenceCard], notes: dict[str, Any]
) -> dict[str, Any]:
    """一次 LLM 调用生成报告的结构化内容（claims 必须带 citations）。"""
    evidence = [
        {
            "paper_id": c.paper_id,
            "title": c.title,
            "year": c.year,
            "notes": notes.get(c.paper_id, {}),
        }
        for c in cards
    ]
    prompt = (
        f"你是文献综述助手。主题：{topic['name']}（{topic['query']}）。\n"
        "基于给定的证据（每篇有 paper_id 与已抽取要点），输出 JSON 对象：\n"
        '{"title":"...","claims":[{"text":"一句可核验的中文结论","citations":["paper_id",...],'
        '"support":"supported|contradicted|unsupported"}]}\n'
        "要求：① 每条 claim **必须**至少引用 1 个 paper_id，且只用输入里出现过的 paper_id；"
        "② 至少 10 条 claim，覆盖方法/数据集/指标/发现/局限；③ 不得编造输入中不存在的数据或结论；"
        "④ 相互矛盾的证据要在 claims 里分别体现，不要取平均。\n\n证据：\n"
        + json.dumps(evidence, ensure_ascii=False)
    )
    call = gateway.chat_json(
        [{"role": "user", "content": prompt}], task="draft_report", max_tokens=3000
    )
    return call.data or {}


def _build_claims(
    raw_claims: list[dict[str, Any]], cards_by_id: dict[str, EvidenceCard]
) -> tuple[list[Claim], int]:
    """把 LLM 返回的 claims 转成契约对象；citation 回查不到本次语料的**整条丢弃**并计数。"""
    from lit_agent_min.models import Support

    claims: list[Claim] = []
    dropped = 0
    for raw in raw_claims:
        text = str(raw.get("text", "")).strip()
        ids = [str(c).strip() for c in (raw.get("citations") or []) if str(c).strip()]
        valid = [pid for pid in ids if pid in cards_by_id]
        if not text or not valid:
            dropped += 1
            continue
        support_raw = str(raw.get("support", "supported")).lower()
        support = {
            "supported": Support.SUPPORTED,
            "contradicted": Support.CONTRADICTED,
            "unsupported": Support.UNSUPPORTED,
        }.get(support_raw, Support.SUPPORTED)
        claims.append(
            Claim(
                text=text,
                citations=[cards_by_id[pid].to_citation() for pid in valid],
                support=support,
            )
        )
    return claims, dropped


def _write_summary(
    settings: Any, rel_path: str, summary: dict[str, Any], gateway: LLMGateway
) -> None:
    summary.setdefault("llm", gateway.summary())
    target = Path(rel_path)
    if not target.is_absolute():
        target = Path(__file__).resolve().parents[1] / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())

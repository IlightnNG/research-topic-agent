"""Phase 2 节点（S2）：S0–S9 十个阶段的实现。

设计约束（来自 phase2 §3 M1 / §10）：
- **节点不写事件、不写锁**：事件由 `runtime/graph_runner.py` 的包装层统一发（保证幂等与可回放）；
- **状态只放引用与计数**，正文留在库里（避免 checkpoint 膨胀）；
- 每个节点返回 `dict` 增量（`stage` / `artifacts` / `counters`），失败用异常表达。
"""

from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import text

from lit_agent.config import Settings
from lit_agent.db.repo import topics as topic_repo
from lit_agent.db.session import connect, make_engine

__all__ = ["PHASE2_STAGES", "Phase2Nodes"]

#: 十节点顺序（S0 → S9）
PHASE2_STAGES: tuple[str, ...] = (
    "intake",
    "scope",
    "retrieval",
    "parse",
    "normalize",
    "mapping",
    "analysis",
    "critique",
    "report",
    "evaluate",
)


class Phase2Nodes:
    """十阶段的实现集合：LangGraph 的节点是这些绑定方法。"""

    def __init__(self, settings: Settings, ctx: Any | None = None) -> None:
        self.settings = settings
        self.ctx = ctx

    # ------------------------------------------------------------------ #
    def _engine(self) -> Any:
        return make_engine(self.settings)

    def _scalar(self, sql: str, params: dict[str, Any] | None = None) -> float:
        engine = self._engine()
        try:
            with connect(engine) as conn:
                return float(conn.execute(text(sql), params or {}).scalar_one_or_none() or 0.0)
        finally:
            engine.dispose()

    # ------------------------------------------------------------------ #
    def intake(self, state: dict[str, Any]) -> dict[str, Any]:
        topic_id = str(state.get("topic_id") or "")
        engine = self._engine()
        try:
            with connect(engine) as conn:
                row = topic_repo.get(conn, topic_id)
        finally:
            engine.dispose()
        if row is None:
            raise ValueError(f"topic 不存在：{topic_id}")
        status = str(dict(row._mapping).get("status") or "active")
        return {
            "stage": "intake",
            "artifacts": {"topic": topic_id, "status": status},
            "counters": {"topic_ok": 1},
        }

    def scope(self, state: dict[str, Any]) -> dict[str, Any]:
        engine = self._engine()
        try:
            with connect(engine) as conn:
                row = conn.execute(
                    text("SELECT scope_statement, scope_keywords_json FROM topics WHERE id = :t"),
                    {"t": state.get("topic_id")},
                ).first()
        finally:
            engine.dispose()
        scope = str(row[0]) if row else ""
        sha = hashlib.sha256(scope.encode("utf-8")).hexdigest()[:12]
        hint = str(state.get("focus_hint") or "")
        return {
            "stage": "scope",
            "artifacts": {"scope_sha": sha, "has_scope": bool(scope), "focus_hint": hint},
            "counters": {"scope_sha_ready": 1},
        }

    def retrieval(self, state: dict[str, Any]) -> dict[str, Any]:
        """检索证据；3.1 起可走 L2（rewrite → hybrid），默认仍是 L1。"""
        from lit_agent.agents.retrieval import select_cards
        from lit_agent.eval import faultinject

        if faultinject.is_active("timeout"):
            from lit_agent.errors import E_SRC_TIMEOUT, LitError

            raise LitError(E_SRC_TIMEOUT, "检索阶段注入超时", context={"stage": "retrieval"})

        from lit_agent.agents.hybrid import hybrid_search

        cards = self._cards()
        query = str(state.get("focus_hint") or "")
        pipeline = getattr(self.ctx, "pipeline", None) or self.settings.pipeline
        l2_steps = 0

        if faultinject.is_active("empty_retrieval"):
            selected = []
            strategy = "fault"
        elif query and bool(getattr(pipeline, "retrieval_l2", False)):
            selected, strategy, l2_steps = self._retrieval_l2(cards, query, pipeline)
        elif query:
            # S7：有聚焦词时走 hybrid（关键词 + char-ngram），无聚焦词回到词面基线
            selected = hybrid_search(
                cards,
                query,
                alpha=float(pipeline.hybrid_alpha),
                min_score=float(pipeline.hybrid_min_score),
            ).cards
            strategy = "hybrid"
        else:
            selected = select_cards(cards, focus_hint=None).cards
            strategy = "keyword"

        artifacts: dict[str, Any] = {
            "candidates": len(cards),
            "paper_ids": [card.paper_id for card in selected],
            "strategy": strategy,
        }
        counters: dict[str, Any] = {"candidates": len(cards), "selected": len(selected)}
        if l2_steps:
            artifacts["l2_steps"] = l2_steps
            counters["l2_steps"] = l2_steps
        return {"stage": "retrieval", "artifacts": artifacts, "counters": counters}

    def _retrieval_l2(
        self, cards: list[Any], query: str, pipeline: Any
    ) -> tuple[list[Any], str, int]:
        """L2：rewrite_query → hybrid_search，失败回到词面基线（显式降级）。"""
        from lit_agent.agents.hybrid import hybrid_search
        from lit_agent.agents.retrieval import select_cards
        from lit_agent.contracts.goals import GOALS
        from lit_agent.runtime.micro_agent import MicroAgent
        from lit_agent.tools.spec import DEFAULT_TOOL_SPECS, ToolRuntime, ToolSpec

        rewritten = {"query": query}
        chosen: list[Any] = []

        def rewrite(*, query: str) -> dict[str, Any]:
            from lit_agent.tools.spec import _rewrite_query

            rewritten["query"] = _rewrite_query(query=query)["query"]
            return {"query": rewritten["query"]}

        def search(*, query: str = "") -> dict[str, Any]:
            nonlocal chosen
            effective = query or rewritten["query"]
            result = hybrid_search(
                cards,
                effective,
                alpha=float(pipeline.hybrid_alpha),
                min_score=float(pipeline.hybrid_min_score),
            )
            chosen = list(result.cards)
            return {"query": effective, "paper_ids": [card.paper_id for card in chosen]}

        runtime = ToolRuntime()
        runtime.register(DEFAULT_TOOL_SPECS["rewrite_query"], rewrite)
        runtime.register(
            ToolSpec(
                name="hybrid_search",
                description="按 query 混合检索证据（k/min_score 由配置）",
                parameters={"query": "string"},
                output_schema={"type": "object", "required": ["paper_ids"]},
                concurrency="parallel",
            ),
            search,
        )

        actions = [
            {"action": "tool", "tool": "rewrite_query", "args": {"query": query}},
            {"action": "tool", "tool": "hybrid_search", "args": {}},
        ]

        def completer(messages: list[dict[str, str]], goal: Any) -> dict[str, Any]:
            if actions:
                return actions.pop(0)
            return {"action": "final", "outputs": {}}

        agent = MicroAgent(
            completer=completer,
            tools=runtime,
            postcondition=lambda loop: (len(chosen) >= 1, []),
            log=getattr(self.ctx, "log", None),
        )
        result = agent.run(GOALS["retrieval"])
        if chosen:
            return chosen, "l2", result.steps_used
        return list(select_cards(cards, focus_hint=query).cards), "l2_fallback", result.steps_used

    def _papers(self, *, focus_hint: str | None = None) -> list[tuple[Any, ...]]:
        engine = self._engine()
        try:
            with connect(engine) as conn:
                return list(
                    conn.execute(
                        text(
                            "SELECT paper_id, title, COALESCE(abstract,''), COALESCE(source,''), year"
                            " FROM papers"
                            " WHERE paper_id NOT IN (SELECT merged_id FROM paper_merges)"
                            " ORDER BY paper_id LIMIT 200"
                        )
                    ).all()
                )
        finally:
            engine.dispose()

    def parse(self, state: dict[str, Any]) -> dict[str, Any]:
        """统计解析状态；`ctx.pdf_enabled` 时对本地文本缓存走一次工具协议。"""
        parsed = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status = 'ok'")
        pending = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status IS NULL")
        failed = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status = 'failed'")
        artifacts: dict[str, Any] = {
            "parsed": int(parsed),
            "pending": int(pending),
            "failed": int(failed),
        }
        counters = {"parse_failed": int(failed)}

        ctx = self.ctx
        if ctx is not None and getattr(ctx, "pdf_enabled", False) and ctx.tools is not None:
            from pathlib import Path as _Path

            cache = _Path(ctx.settings.storage.data_root) / "pdf_texts"
            used = 0
            if cache.exists():
                for text_file in sorted(cache.glob("*.txt"))[:3]:
                    result = ctx.tools.call(
                        "paper_pdf",
                        log=ctx.log,
                        paper_id=text_file.stem,
                        text=text_file.read_text(encoding="utf-8"),
                    )
                    used += 1 if result.ok else 0
            artifacts["pdf_tools"] = used
            counters["pdf_tools"] = used
        return {"stage": "parse", "artifacts": artifacts, "counters": counters}

    def normalize(self, state: dict[str, Any]) -> dict[str, Any]:
        from lit_agent.sources.dedup import run_dedup

        result = run_dedup(self.settings)
        return {
            "stage": "normalize",
            "artifacts": {"unique": int(result["unique"]), "merged_pairs": int(result["merged_pairs"])},
            "counters": {"merged_pairs": int(result["merged_pairs"])},
        }

    def mapping(self, state: dict[str, Any]) -> dict[str, Any]:
        from lit_agent.sources.dedup import project_citations

        projection = project_citations(self.settings)
        return {
            "stage": "mapping",
            "artifacts": {"citation_edges": int(projection["edges_total"])},
            "counters": {"citation_edges": int(projection["edges_total"])},
        }

    def analysis(self, state: dict[str, Any]) -> dict[str, Any]:
        """S6：analyst agent 抽取 claims（有 key 时走 LLM，失败回落确定性）。"""
        from lit_agent.agents.analyst import analyze, claims_to_json
        from lit_agent.eval import faultinject

        cards = self._cards_by_ids(self._paper_ids(state))
        gateway = getattr(self.ctx, "gateway", None) if self.ctx is not None else None
        claims = analyze(cards, gateway=gateway)
        if faultinject.is_active("bad_artifact") and claims:
            # 注入：把第一条改成"无引用"，用来验证 critic 会拦住
            from lit_agent.models.claim import Claim
            from lit_agent.models.evidence import Support

            claims = [Claim(text=claims[0].text, citations=[], support=Support.UNSUPPORTED), *claims[1:]]
        used_llm = gateway is not None
        pipeline = getattr(self.ctx, "pipeline", None) or self.settings.pipeline
        repair: dict[str, int] = {}
        if bool(getattr(pipeline, "analysis_l2", False)) and claims:
            claims, repair = self._analysis_l2(claims)

        from lit_agent.eval.scope_drift import drift_for

        self._topic_id = str(state.get("topic_id") or "")
        gates_cfg = getattr(getattr(self.ctx, "pipeline", None), "gates", None) \
            or self.settings.pipeline.gates
        drift = drift_for(
            self._scope_text(),
            [claim.text for claim in claims],
            warn_below=float(gates_cfg.drift_warn_below),
            block_below=float(gates_cfg.drift_block_below),
        )
        counters = {"claims": len(claims), "cards": len(cards)}
        counters.update(repair)
        if drift.warning:
            counters["drift_warn"] = 1
        if drift.blocked:
            counters["drift_block"] = 1
        return {
            "stage": "analysis",
            "artifacts": {
                "claims": len(claims),
                "claims_json": claims_to_json(claims),
                "llm_used": used_llm,
                "extraction": "llm" if used_llm else "deterministic",
                "analysis_l2": bool(repair),
                "repair": repair,
                "drift_verdict": drift.verdict,
                "drift_coverage": drift.coverage,
            },
            "counters": counters,
        }

    def _analysis_l2(self, claims: list[Any]) -> tuple[list[Any], dict[str, int]]:
        """L2：逐条 verify → 失败 rewrite → 仍失败丢弃（只改坏 claim）。"""
        from lit_agent.tools.spec import tool_runtime_for

        runtime = tool_runtime_for(("verify_claim", "rewrite_claim"))
        log = getattr(self.ctx, "log", None)
        kept: list[Any] = []
        rewritten = 0
        dropped = 0

        for claim in claims:
            snippet = claim.citations[0].snippet if claim.citations else ""
            verdict = runtime.call(
                "verify_claim",
                args={"text": claim.text, "snippet": snippet or ""},
                log=log,
            )
            supported = bool(verdict.output.get("supported")) if verdict.ok else False

            if not supported and snippet:
                fixed = runtime.call(
                    "rewrite_claim",
                    args={"text": claim.text, "snippet": snippet},
                    log=log,
                )
                new_text = str(fixed.output.get("text") or "") if fixed.ok else ""
                if new_text and new_text != claim.text:
                    recheck = runtime.call(
                        "verify_claim",
                        args={"text": new_text, "snippet": snippet},
                        log=log,
                    )
                    if recheck.ok and bool(recheck.output.get("supported")):
                        claim = claim.model_copy(update={"text": new_text})
                        rewritten += 1
                        supported = True

            if supported:
                kept.append(claim)
            else:
                dropped += 1

        return kept, {
            "claims_verified": len(claims),
            "claims_rewritten": rewritten,
            "claims_dropped": dropped,
        }

    def _scope_text(self) -> str:
        """读 topic scope；漂移检测是**尽力而为**，读不到就跳过（不阻断主流程）。"""
        engine = self._engine()
        try:
            with connect(engine) as conn:
                row = conn.execute(
                    text("SELECT scope_statement FROM topics WHERE id = :t"),
                    {"t": self._topic_id},
                ).first()
        except Exception:  # noqa: BLE001 - 漂移检测失败不应影响分析
            return ""
        finally:
            engine.dispose()
        return str(row[0]) if row and row[0] else ""

    def _paper_ids(self, state: dict[str, Any]) -> list[str]:
        artifacts = state.get("artifacts") or {}
        ids = artifacts.get("paper_ids") or []
        return [str(item) for item in ids]

    def _cards_by_ids(self, paper_ids: list[str]) -> list[Any]:
        from lit_agent.models.evidence import EvidenceCard

        if not paper_ids:
            return []
        from sqlalchemy import bindparam

        engine = self._engine()
        try:
            with connect(engine) as conn:
                rows = conn.execute(
                    text(
                        "SELECT paper_id, title, COALESCE(abstract,''), COALESCE(source,''), year"
                        " FROM papers WHERE paper_id IN :ids"
                    ).bindparams(bindparam("ids", expanding=True)),
                    {"ids": paper_ids},
                ).all()
        finally:
            engine.dispose()
        cards: list[Any] = []
        for paper_id, title, abstract, source, year in rows:
            snippet = (abstract or title or "").strip()[:400]
            if snippet:
                cards.append(
                    EvidenceCard(
                        paper_id=str(paper_id),
                        title=str(title or paper_id),
                        snippet=snippet,
                        source=str(source or "unknown"),
                        year=int(year) if year is not None else None,
                    )
                )
        return cards

    def _cards(self) -> list[Any]:
        from lit_agent.models.evidence import EvidenceCard

        cards: list[Any] = []
        for paper_id, title, abstract, source, year in self._papers():
            snippet = (abstract or title or "").strip()[:400]
            if snippet:
                cards.append(
                    EvidenceCard(
                        paper_id=str(paper_id),
                        title=str(title or paper_id),
                        snippet=snippet,
                        source=str(source or "unknown"),
                        year=int(year) if year is not None else None,
                    )
                )
        return cards

    def critique(self, state: dict[str, Any]) -> dict[str, Any]:
        """S6：critic agent 做结构自查（缺引用/重复/比例），产出 GuardVerdict。"""
        from lit_agent.agents.analyst import claims_from_json
        from lit_agent.agents.critic import critique as critique_claims

        claims = claims_from_json(self._claims_json(state))
        verdict = critique_claims(claims)
        return {
            "stage": "critique",
            "artifacts": {"degraded": not verdict.ok, "verdict": verdict.model_dump(mode="json")},
            "counters": {
                "critique_degraded": int(not verdict.ok),
                "unresolved_citations": 1 if verdict.code == "E_GROUND_UNRESOLVED_CITATION" else 0,
            },
        }

    def _claims_json(self, state: dict[str, Any]) -> str:
        return str((state.get("artifacts") or {}).get("claims_json") or "[]")

    def report(self, state: dict[str, Any]) -> dict[str, Any]:
        """两阶段：这里只声明写入，门禁通过后由 commit 落库。"""
        from lit_agent.agents.analyst import claims_from_json

        claims = claims_from_json(self._claims_json(state))
        if self.settings.report.v2_enabled:
            from lit_agent.report.assemble import build_report_bundle

            draft, report_context = build_report_bundle(
                self.settings,
                run_id=str(state.get("run_id") or ""),
                topic_id=str(state.get("topic_id") or ""),
                paper_ids=self._paper_ids(state),
                title=f"Weekly report: {state.get('topic_id')}",
                gateway=getattr(self.ctx, "gateway", None),
            )
            from lit_agent.report.cards import source_sha

            cards_payload = [
                {
                    "paper_id": card.paper_id,
                    "content_sha": source_sha(card.title, card.abstract),
                    "card": card.to_dict(),
                }
                for card in report_context.cards
                if self.settings.report.cache
            ]
            return {
                "stage": "report",
                "artifacts": {
                    "claims": len(claims),
                    "report_sections": len(draft.sections),
                    "report_generated_by": draft.generated_by,
                    "report_word_count": draft.word_count,
                    "report_draft_json": draft.model_dump(mode="json"),
                    "report_cards_json": cards_payload,
                },
                "counters": {"report_written": 0},
                "pending_writes": [{"kind": "report"}],
            }
        return {
            "stage": "report",
            "artifacts": {"claims": len(claims)},
            "counters": {"report_written": 0},
            "pending_writes": [{"kind": "report"}],
        }

    def evaluate(self, state: dict[str, Any]) -> dict[str, Any]:
        from lit_agent.eval.metrics import compute_run_metrics

        metrics = compute_run_metrics(self.settings, str(state.get("run_id")))
        return {
            "stage": "evaluate",
            "artifacts": {
                "claims_total": metrics["claims_total"],
                "grounding_rate": metrics["grounding_rate"],
                "cost_usd": metrics["cost_usd"],
            },
            "counters": {"eval_done": 1},
            "pending_writes": [{"kind": "metrics"}],
        }

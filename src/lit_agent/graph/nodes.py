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

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

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
        """取主记录论文作为候选证据（S10 会替换为 hybrid 检索）。"""
        rows = self._papers()
        return {
            "stage": "retrieval",
            "artifacts": {"candidates": len(rows), "paper_ids": [row[0] for row in rows][:200]},
            "counters": {"candidates": len(rows)},
        }

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
        parsed = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status = 'ok'")
        pending = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status IS NULL")
        failed = self._scalar("SELECT COUNT(*) FROM papers WHERE parse_status = 'failed'")
        return {
            "stage": "parse",
            "artifacts": {"parsed": int(parsed), "pending": int(pending), "failed": int(failed)},
            "counters": {"parse_failed": int(failed)},
        }

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
        """把候选论文折成 claims（S6 会换成 LLM 抽取 + 判定器）。"""
        from lit_agent.agents.reporter import build_report

        cards = self._cards()
        draft = build_report(cards, topic_id=str(state.get("topic_id")), run_id=str(state.get("run_id")))
        return {
            "stage": "analysis",
            "artifacts": {"claims": draft.n_claims, "cards": len(cards)},
            "counters": {"claims": draft.n_claims, "cards": len(cards)},
        }

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
        counters = dict(state.get("counters") or {})
        claims = int(counters.get("claims", 0))
        degraded = claims == 0
        return {
            "stage": "critique",
            "artifacts": {"degraded": degraded, "verdict": "warn" if degraded else "ok"},
            "counters": {"critique_degraded": int(degraded)},
        }

    def report(self, state: dict[str, Any]) -> dict[str, Any]:
        from lit_agent.runtime.runner import persist_report_for_state

        report_id = persist_report_for_state(self.settings, state)
        return {
            "stage": "report",
            "artifacts": {"report_id": report_id},
            "counters": {"report_written": 1},
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
        }

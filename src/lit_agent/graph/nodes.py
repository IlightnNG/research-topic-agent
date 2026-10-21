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
        """S5：由 retrieval agent 选证据；S10 替换为 hybrid。"""
        from lit_agent.agents.retrieval import select_cards
        from lit_agent.eval import faultinject

        if faultinject.is_active("timeout"):
            from lit_agent.errors import E_SRC_TIMEOUT, LitError

            raise LitError(E_SRC_TIMEOUT, "检索阶段注入超时", context={"stage": "retrieval"})

        cards = self._cards()
        if faultinject.is_active("empty_retrieval"):
            selected = []
        else:
            selected = select_cards(cards, focus_hint=state.get("focus_hint")).cards
        return {
            "stage": "retrieval",
            "artifacts": {"candidates": len(cards), "paper_ids": [card.paper_id for card in selected]},
            "counters": {"candidates": len(cards), "selected": len(selected)},
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
        """S6：analyst agent 抽取 claims（有 key 时走 LLM，失败回落确定性）。"""
        from lit_agent.agents.analyst import analyze, claims_to_json
        from lit_agent.eval import faultinject

        cards = self._cards_by_ids(self._paper_ids(state))
        claims = analyze(cards)
        if faultinject.is_active("bad_artifact") and claims:
            # 注入：把第一条改成"无引用"，用来验证 critic 会拦住
            from lit_agent.models.claim import Claim
            from lit_agent.models.evidence import Support

            claims = [Claim(text=claims[0].text, citations=[], support=Support.UNSUPPORTED), *claims[1:]]
        return {
            "stage": "analysis",
            "artifacts": {"claims": len(claims), "claims_json": claims_to_json(claims)},
            "counters": {"claims": len(claims), "cards": len(cards)},
        }

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
        from lit_agent.agents.analyst import claims_from_json
        from lit_agent.runtime.runner import persist_report_from_claims

        claims = claims_from_json(self._claims_json(state))
        report_id = persist_report_from_claims(
            self.settings,
            str(state.get("run_id")),
            str(state.get("topic_id")),
            claims,
            focus_hint=state.get("focus_hint"),
        )
        return {
            "stage": "report",
            "artifacts": {"report_id": report_id, "claims": len(claims)},
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

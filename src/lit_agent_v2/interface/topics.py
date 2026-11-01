"""Topic scope storage for the report interface."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from lit_agent_v2.storage.db import Database

__all__ = ["TopicStore"]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _loads(raw: str | None, default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return default


def make_brief(topic: dict[str, Any]) -> dict[str, Any]:
    direction = str(topic.get("direction") or "")
    description = str(topic.get("description") or "").strip()
    keywords = list(topic.get("keywords") or [])
    exclusions = list(topic.get("exclusions") or [])
    constraints = list(topic.get("constraints") or [])
    scope = description or direction
    return {
        "topic_id": str(topic["id"]),
        "normalized_title": f"{direction}: scoped research brief",
        "scope_statement": f"{scope} Stay within {direction}.",
        "include_criteria": [
            f"Directly relevant to {direction}",
            *[f"Mentions {keyword}" for keyword in keywords],
            *constraints,
        ],
        "exclude_criteria": exclusions,
        "search_queries": [
            f"{direction} review",
            f"{direction} {keywords[0] if keywords else 'methods'}",
            f"{direction} evaluation",
        ],
        "language": "en",
        "created_at": _now(),
    }


class TopicStore:
    def __init__(self, db: Database) -> None:
        self.db = db
        self._seed()

    def _seed(self) -> None:
        with self.db.connect() as conn:
            count = conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0]
            if count:
                return
            seeds = [
                (
                    "topic-ai-agents",
                    "AI agents",
                    "Tool-using language agents, planning, evaluation, and multi-agent systems.",
                    ["LLM agents", "tool use", "planning", "multi-agent"],
                    ["robotics control"],
                    ["peer reviewed", "2020+"],
                ),
                (
                    "topic-fpga",
                    "FPGA acceleration",
                    "FPGA-based acceleration for machine learning and scientific workloads.",
                    ["FPGA", "HLS", "accelerator", "hardware"],
                    ["ASIC-only"],
                    [],
                ),
                (
                    "topic-rag",
                    "Scientific RAG",
                    "Retrieval-augmented generation for scientific literature and citation quality.",
                    ["retrieval", "citation", "scientific writing"],
                    [],
                    [],
                ),
            ]
            for topic_id, direction, description, keywords, exclusions, constraints in seeds:
                topic = {
                    "id": topic_id,
                    "direction": direction,
                    "description": description,
                    "keywords": keywords,
                    "exclusions": exclusions,
                    "constraints": constraints,
                }
                conn.execute(
                    "INSERT OR IGNORE INTO topics"
                    "(id,direction,description,keywords_json,exclusions_json,constraints_json,brief_json,created_at)"
                    " VALUES (?,?,?,?,?,?,?,?)",
                    (
                        topic_id,
                        direction,
                        description,
                        json.dumps(keywords, ensure_ascii=False),
                        json.dumps(exclusions, ensure_ascii=False),
                        json.dumps(constraints, ensure_ascii=False),
                        json.dumps(make_brief(topic), ensure_ascii=False),
                        _now(),
                    ),
                )

    def list(self) -> list[dict[str, Any]]:
        with self.db.connect() as conn:
            rows = conn.execute("SELECT * FROM topics ORDER BY created_at").fetchall()
        return [self._topic(row) for row in rows]

    def get(self, topic_id: str) -> dict[str, Any] | None:
        with self.db.connect() as conn:
            row = conn.execute("SELECT * FROM topics WHERE id=?", (topic_id,)).fetchone()
        return self._topic(row) if row else None

    def create(
        self,
        *,
        direction: str,
        description: str | None = None,
        keywords: list[str] | None = None,
        exclusions: list[str] | None = None,
        constraints: list[str] | None = None,
    ) -> dict[str, Any]:
        topic_id = f"topic-{uuid.uuid4().hex[:10]}"
        topic = {
            "id": topic_id,
            "direction": direction.strip(),
            "description": description.strip() if description else "",
            "keywords": keywords or [],
            "exclusions": exclusions or [],
            "constraints": constraints or [],
        }
        brief = make_brief(topic)
        with self.db.connect() as conn:
            conn.execute(
                "INSERT INTO topics"
                "(id,direction,description,keywords_json,exclusions_json,constraints_json,brief_json,created_at)"
                " VALUES (?,?,?,?,?,?,?,?)",
                (
                    topic_id,
                    topic["direction"],
                    topic["description"],
                    json.dumps(topic["keywords"], ensure_ascii=False),
                    json.dumps(topic["exclusions"], ensure_ascii=False),
                    json.dumps(topic["constraints"], ensure_ascii=False),
                    json.dumps(brief, ensure_ascii=False),
                    _now(),
                ),
            )
        return {**topic, "created_at": _now()}

    def brief(self, topic_id: str) -> dict[str, Any] | None:
        topic = self.get(topic_id)
        if topic is None:
            return None
        with self.db.connect() as conn:
            row = conn.execute("SELECT brief_json FROM topics WHERE id=?", (topic_id,)).fetchone()
        raw = _loads(row["brief_json"] if row else None, None)
        if not raw:
            raw = make_brief(topic)
            with self.db.connect() as conn:
                conn.execute(
                    "UPDATE topics SET brief_json=? WHERE id=?",
                    (json.dumps(raw, ensure_ascii=False), topic_id),
                )
        return raw

    @staticmethod
    def _topic(row: Any) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "direction": str(row["direction"]),
            "description": str(row["description"] or ""),
            "keywords": _loads(row["keywords_json"], []),
            "exclusions": _loads(row["exclusions_json"], []),
            "constraints": _loads(row["constraints_json"], []),
            "created_at": str(row["created_at"]),
        }

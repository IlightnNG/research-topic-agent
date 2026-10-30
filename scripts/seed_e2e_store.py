"""Seed an isolated E2E store (3 fixture papers + one report).

Used by Playwright's backend webServer with LIT_AGENT_STORAGE__DATA_ROOT set
to a dedicated directory, so live papers never leak into E2E.
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.db.repo import papers as paper_repo  # noqa: E402
from lit_agent.db.repo import topics as topic_repo  # noqa: E402
from lit_agent.db.session import connect, make_engine, upgrade_database  # noqa: E402
from lit_agent.models.paper import Paper  # noqa: E402
from lit_agent.models.topic import Topic  # noqa: E402
from lit_agent.runtime.graph_runner import run_graph  # noqa: E402


def main() -> int:
    settings = load_settings()
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
            topic_repo.upsert(
                conn,
                Topic(
                    id="e2e-topic",
                    name="E2E Topic",
                    scope_statement="llm agents for e2e testing",
                ),
            )
            paper_repo.upsert_many(
                conn,
                [
                    Paper(
                        paper_id=f"E2E-P{index}",
                        title=f"E2E paper {index}: tool use in agents",
                        abstract="tool use improves task success and reliability of LLM agents",
                        source="e2e",
                    )
                    for index in range(3)
                ],
            )
    finally:
        engine.dispose()

    result = run_graph(
        settings,
        "e2e-topic",
        run_id=f"e2e-seed-{uuid.uuid4().hex[:8]}",
    )
    if result.get("state") != "succeeded":
        print(f"seed run failed: {result.get('state')}", file=sys.stderr)
        return 1
    print("seeded isolated e2e store")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""E2E 数据种子：给 e2e-topic 准备 3 篇可引用论文（幂等）。

用法：uv run python scripts/seed_e2e.py
说明：当前 schema 的证据表是全局的（无 topic_papers 关联），
所以 Chat/报告的检索都基于全局 papers；e2e 只需要有可命中的片段。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lit_agent.config import load_settings  # noqa: E402
from lit_agent.db.repo import papers as paper_repo  # noqa: E402
from lit_agent.db.session import connect, make_engine, upgrade_database  # noqa: E402
from lit_agent.models.paper import Paper  # noqa: E402


def main() -> int:
    settings = load_settings()
    upgrade_database(settings)
    engine = make_engine(settings)
    try:
        with connect(engine, immediate=True) as conn:
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
    print("seeded 3 papers (E2E-P0..P2)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""V2 CLI."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from lit_agent_v2.composition import build_report_workflow_from_path
from lit_agent_v2.contracts import RunRequest
from lit_agent_v2.run_shell import RunShell
from lit_agent_v2.storage.artifacts import ArtifactStore
from lit_agent_v2.storage.db import Database

__all__ = ["main"]


def main() -> int:
    parser = argparse.ArgumentParser(description="lit-agent v2")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run")
    run.add_argument("--topic", required=True)
    run.add_argument("--limit", type=int, default=100)
    run.add_argument("--corpus", required=True)
    run.add_argument("--db", default="D:/lit-agent-store/v2/v2.sqlite")
    args = parser.parse_args()

    db = Database(args.db)
    db.migrate()
    shell = RunShell(db, ArtifactStore(Path(args.db).parent / "artifacts"))
    outcome = build_report_workflow_from_path(shell, args.corpus).run(
        RunRequest(topic_id=args.topic, limit=args.limit)
    )
    print(
        json.dumps(
            {
                "run_id": outcome.run_id,
                "report_id": outcome.report_id,
                "state": outcome.draft.state,
                "words": outcome.draft.word_count,
                "directions": len(outcome.mapping.directions),
            },
            indent=2,
        )
    )
    return 0

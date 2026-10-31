"""V2 SQLite storage (greenfield schema)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

__all__ = ["Database"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY,
  topic_id TEXT NOT NULL,
  workflow TEXT NOT NULL,
  request_json TEXT,
  state TEXT NOT NULL,
  phase TEXT,
  config_hash TEXT,
  model TEXT,
  prompt_version TEXT,
  embedding_model TEXT,
  seed INTEGER,
  created_at TEXT NOT NULL,
  started_at TEXT,
  finished_at TEXT,
  error_code TEXT
);

CREATE TABLE IF NOT EXISTS run_nodes (
  run_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  state TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 0,
  checkpoint_json TEXT,
  artifact_sha TEXT,
  started_at TEXT,
  finished_at TEXT,
  error_code TEXT,
  PRIMARY KEY (run_id, node_id)
);

CREATE TABLE IF NOT EXISTS run_artifacts (
  run_id TEXT NOT NULL,
  node_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (run_id, node_id, kind, sha256)
);

CREATE TABLE IF NOT EXISTS run_events (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  seq INTEGER NOT NULL,
  type TEXT NOT NULL,
  node_id TEXT,
  payload_json TEXT NOT NULL,
  ts TEXT NOT NULL,
  UNIQUE (run_id, seq)
);


CREATE TABLE IF NOT EXISTS reports (
  report_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  topic_id TEXT NOT NULL,
  title TEXT NOT NULL,
  content_md TEXT NOT NULL,
  content_sha TEXT NOT NULL,
  state TEXT NOT NULL,
  word_count INTEGER NOT NULL,
  n_claims INTEGER NOT NULL,
  metrics_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS report_sections (
  report_id TEXT NOT NULL,
  section_id TEXT NOT NULL,
  kind TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  claim_indexes_json TEXT NOT NULL,
  ord INTEGER NOT NULL,
  PRIMARY KEY (report_id, section_id)
);

CREATE TABLE IF NOT EXISTS claims (
  claim_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  paper_id TEXT NOT NULL,
  text TEXT NOT NULL,
  quote TEXT NOT NULL,
  section TEXT,
  page INTEGER,
  support TEXT,
  confidence REAL
);

CREATE TABLE IF NOT EXISTS citations (
  report_id TEXT NOT NULL,
  section_id TEXT NOT NULL,
  claim_id TEXT NOT NULL,
  paper_id TEXT NOT NULL,
  quote TEXT NOT NULL
);


CREATE TABLE IF NOT EXISTS chat_sessions (
  id TEXT PRIMARY KEY,
  topic_id TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_messages (
  id TEXT PRIMARY KEY,
  session_id TEXT NOT NULL,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  citations_json TEXT,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS metric_points (
  id TEXT PRIMARY KEY,
  metric_id TEXT NOT NULL,
  version TEXT NOT NULL,
  run_id TEXT,
  node_id TEXT,
  step TEXT,
  value REAL,
  numerator REAL,
  denominator REAL,
  sample_size INTEGER,
  config_hash TEXT,
  model TEXT,
  prompt_version TEXT,
  dataset TEXT,
  ts TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS run_spans (
  span_id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  node_id TEXT,
  step TEXT,
  name TEXT NOT NULL,
  status TEXT NOT NULL,
  start_ts TEXT NOT NULL,
  end_ts TEXT,
  duration_ms INTEGER,
  attributes_json TEXT,
  error_code TEXT
);

CREATE TABLE IF NOT EXISTS experiments (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  config_json TEXT NOT NULL,
  config_hash TEXT NOT NULL,
  dataset TEXT,
  baseline_run_id TEXT,
  candidate_run_id TEXT,
  score REAL,
  hard_fail_json TEXT,
  status TEXT NOT NULL,
  created_at TEXT NOT NULL
);
"""


class Database:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def migrate(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)

    def table_names(self) -> set[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        return {str(row[0]) for row in rows}

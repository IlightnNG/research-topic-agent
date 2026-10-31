"""Content-addressed artifact store."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

__all__ = ["ArtifactStore"]


class ArtifactStore:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put(self, payload: dict[str, Any]) -> str:
        body = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
        target = self.root / f"{digest}.json"
        if not target.exists():
            target.write_text(body, encoding="utf-8")
        return digest

    def get(self, sha: str) -> dict[str, Any]:
        target = self.root / f"{sha}.json"
        if not target.exists():
            raise FileNotFoundError(sha)
        return json.loads(target.read_text(encoding="utf-8"))

    def exists(self, sha: str) -> bool:
        return (self.root / f"{sha}.json").exists()

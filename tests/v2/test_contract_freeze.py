"""Legacy 1.2 contract freeze guard.

2.0 draft contracts are intentionally outside this snapshot until frozen.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from lit_agent_v2.contracts.version import CONTRACT_HASH, CONTRACT_VERSION, SCHEMA_VERSION


def _hash() -> str:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2" / "contracts"
    legacy = {"__init__.py", "errors.py", "events.py", "ports.py", "report.py"}
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        if path.name in {"version.py"} or path.name not in legacy:
            continue
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_contract_version_frozen() -> None:
    assert CONTRACT_VERSION == "1.2"
    assert SCHEMA_VERSION == 1
    assert _hash() == CONTRACT_HASH

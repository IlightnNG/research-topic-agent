"""Contract freeze guard.

If this test fails, a contract file changed without a deliberate version bump.
Update CONTRACT_HASH and docs/CONTRACTS.md / DECISIONS.md together.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from lit_agent_v2.contracts.version import CONTRACT_HASH, CONTRACT_VERSION, SCHEMA_VERSION


def _hash() -> str:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2" / "contracts"
    digest = hashlib.sha256()
    for path in sorted(root.glob("*.py")):
        if path.name == "version.py":
            continue
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def test_contract_version_frozen() -> None:
    assert CONTRACT_VERSION == "1.0"
    assert SCHEMA_VERSION == 1
    assert _hash() == CONTRACT_HASH

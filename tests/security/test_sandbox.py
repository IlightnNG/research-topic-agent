"""3.4 / S19：沙盒准入（命令白名单 / 路径越界）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from lit_agent.errors import E_PERMISSION_REQUIRED, LitError
from lit_agent.security.sandbox import check_command, ensure_within


def test_allowlisted_command_passes() -> None:
    check_command(["python", "-V"])
    check_command(["pytest", "-q", "tests/chat"])


def test_unknown_command_is_rejected() -> None:
    with pytest.raises(LitError) as excinfo:
        check_command(["rm", "-rf", "/"])
    assert excinfo.value.code == E_PERMISSION_REQUIRED


def test_network_command_denied_by_default() -> None:
    with pytest.raises(LitError):
        check_command(["curl", "http://example.com"])
    check_command(["curl", "http://example.com"], allow_network=True, allowlist=frozenset({"curl"}))


def test_shell_metacharacters_rejected() -> None:
    with pytest.raises(LitError):
        check_command(["python", "-c", "print(1); import os"])


def test_ensure_within_blocks_traversal(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    assert ensure_within(root, Path("a.txt")) == (root / "a.txt").resolve()
    with pytest.raises(LitError):
        ensure_within(root, Path("../etc/passwd"))

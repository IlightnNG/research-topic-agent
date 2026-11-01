"""Phase 4.1 cleanup guard: no legacy workflow imports or files."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "lit_agent_v2"
TESTS = ROOT / "tests"

FORBIDDEN = (
    "lit_agent_v2.domains.report",
    "lit_agent_v2.contracts.ports",
    "lit_agent_v2.run_shell",
    "lit_agent_v2.workflow.runner",
    "lit_agent_v2.workflow.verifier",
    "lit_agent_v2.kernel.tools",
    "lit_agent_v2.kernel.loop",
    "ReportWorkflow",
    "WriteService",
)


def test_no_legacy_modules() -> None:
    assert not (SRC / "run_shell.py").exists()
    assert not (SRC / "domains" / "report").exists()
    assert not (SRC / "contracts" / "ports.py").exists()
    assert not (SRC / "workflow" / "runner.py").exists()
    assert not (SRC / "workflow" / "verifier.py").exists()
    assert not (SRC / "kernel" / "tools.py").exists()
    assert not (SRC / "kernel" / "loop.py").exists()


def test_no_legacy_imports() -> None:
    hits: list[str] = []
    for path in sorted([*SRC.rglob("*.py"), *TESTS.rglob("*.py")]):
        if path.name == "test_no_legacy_imports.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in FORBIDDEN:
            if token in text:
                hits.append(f"{path.relative_to(ROOT)}: {token}")
    assert not hits, "\n".join(hits)

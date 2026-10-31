"""Module boundary / composition tests."""

from __future__ import annotations

import ast
from pathlib import Path


def _imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
        elif isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
    return modules


def test_report_workflow_only_depends_on_ports_and_own_module() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2"
    imports = _imports(root / "domains" / "report" / "workflow.py")
    forbidden = {
        "lit_agent_v2.domains.report.source",
        "lit_agent_v2.domains.report.evidence",
        "lit_agent_v2.domains.report.ingest",
        "lit_agent_v2.domains.report.persist",
    }
    assert not (imports & forbidden)


def test_evaluation_runner_does_not_depend_on_report_implementation() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2"
    imports = _imports(root / "evaluation" / "runner.py")
    assert not any(module.startswith("lit_agent_v2.domains.report") for module in imports)


def test_api_does_not_construct_report_workflow_directly() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2"
    imports = _imports(root / "api" / "app.py")
    assert "lit_agent_v2.domains.report.workflow" not in imports
    assert "lit_agent_v2.domains.report.ingest" not in imports


def test_composition_is_the_wiring_point() -> None:
    root = Path(__file__).resolve().parents[2] / "src" / "lit_agent_v2"
    composition = _imports(root / "composition.py")
    assert "lit_agent_v2.domains.report.source" in composition
    assert "lit_agent_v2.domains.report.evidence" in composition
    assert "lit_agent_v2.domains.report.workflow" in composition

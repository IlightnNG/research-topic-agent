"""Phase 2 基线验证器（S1）。

用途：把 Phase 2 的"能力缺口"变成**可执行的红绿表**。
- 现在（P2 起点）大部分断言应当是 **RED**——这是刻意的：它们就是 S2–S12 的验收目标。
- 每次改完一步，重跑本脚本，对应的 RED 应该变 GREEN；**不允许为了变绿而放松断言**。

用法：
    uv run python scripts/verify_phase2.py --offline
    uv run python scripts/verify_phase2.py --offline --baseline   # 允许 RED，仅存基线
    uv run python scripts/verify_phase2.py --online               # 额外跑真实数据回归

退出码：默认全绿才 0；`--baseline` 时总是 0。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# 期望的十节点（S2 目标）
EXPECTED_STAGES = (
    "intake",
    "scope",
    "retrieval",
    "parse",
    "normalize",
    "mapping",
    "analysis",
    "critique",
    "report",
    "evaluate",
)


@dataclass
class Result:
    name: str
    ok: bool
    detail: str
    target: str
    seconds: float = 0.0


@dataclass
class Report:
    results: list[Result] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, target: str, seconds: float = 0.0) -> None:
        self.results.append(Result(name, ok, detail, target, seconds))

    @property
    def greens(self) -> int:
        return sum(1 for item in self.results if item.ok)

    def emit(self, path: Path | None, *, baseline: bool) -> None:
        width = max(len(item.name) for item in self.results)
        print("\nPhase 2 capability baseline")
        print("-" * (width + 78))
        for item in self.results:
            flag = "PASS" if item.ok else "RED "
            print(f"[{flag}] {item.name.ljust(width)}  {item.detail}   → 目标: {item.target}")
        print("-" * (width + 78))
        reds = len(self.results) - self.greens
        print(f"TOTAL: {self.greens}/{len(self.results)} PASS, {reds} RED" + (" (baseline mode)" if baseline else ""))
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {
                        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                        "baseline": baseline,
                        "greens": self.greens,
                        "reds": reds,
                        "results": [
                            {"name": r.name, "ok": r.ok, "detail": r.detail, "target": r.target}
                            for r in self.results
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
            print(f"report: {path}")


# --------------------------------------------------------------------------- #
# 探针
# --------------------------------------------------------------------------- #
def probe_graph_nodes() -> tuple[bool, str]:
    """十节点是否就位（S2）。"""
    from lit_agent.graph.nodes import PHASE2_STAGES

    missing = [name for name in EXPECTED_STAGES if name not in PHASE2_STAGES]
    return len(PHASE2_STAGES) == 10 and not missing, f"stages={len(PHASE2_STAGES)} missing={missing or '-'}"


def probe_graph_edges() -> tuple[bool, str]:
    """E1–E13 是否都有判定规则（S3）。"""
    from lit_agent.graph.edges import EDGES, RULES

    covered = {rule.edge for rule in RULES}
    missing = sorted(set(EDGES) - covered)
    return not missing and len(covered) == 13, f"rules={len(covered)}/13 missing={missing or '-'}"


def probe_resume() -> tuple[bool, str]:
    """断点续跑（S4）：执行器支持 `resume=True` 且提供崩溃注入（可被测试验证）。"""
    import inspect

    from lit_agent.runtime import graph_runner

    signature = inspect.signature(graph_runner.run_graph)
    has_resume = "resume" in signature.parameters
    has_crash = hasattr(graph_runner, "SimulatedCrash")
    return has_resume and has_crash, f"resume={has_resume} crash_hook={has_crash}"


def probe_agents() -> tuple[bool, str]:
    """四角色是否实现（S5/S6）。"""
    from lit_agent.errors import FeatureDisabledError

    roles = {
        "retrieval": ("lit_agent.agents.retrieval", "run_retrieval"),
        "mapper": ("lit_agent.agents.mapper", "map_papers"),
        "analyst": ("lit_agent.agents.analyst", "analyze"),
        "critic": ("lit_agent.agents.critic", "critique"),
    }
    implemented: list[str] = []
    for role, (module_name, func_name) in roles.items():
        try:
            module = __import__(module_name, fromlist=[func_name])
            func = getattr(module, func_name)
            try:
                func()
            except FeatureDisabledError:
                continue
            except Exception:  # noqa: BLE001 - 有实现但参数不对，也算已实现
                implemented.append(role)
                continue
        except AttributeError:
            continue
    return len(implemented) == len(roles), f"implemented={implemented}"


def probe_folding() -> tuple[bool, str]:
    """摘要折叠（S7）。"""
    from lit_agent.context.folding import folding_for
    from lit_agent.errors import LitError

    try:
        strategy = folding_for("summarize")
    except LitError:
        return False, "summarize=not implemented"
    return callable(getattr(strategy, "fold", None)), f"strategy={type(strategy).__name__}"


def probe_guards() -> tuple[bool, str]:
    """15 类守卫（S8）。"""
    import inspect

    from lit_agent.graph import guards

    classes = [
        name
        for name, obj in vars(guards).items()
        if inspect.isclass(obj) and name.endswith("Guard") and obj.__module__ == guards.__name__
    ]
    return len(classes) >= 15, f"guards={len(classes)} ({', '.join(sorted(classes))[:80]})"


def probe_runtime_control() -> tuple[bool, str]:
    """pause / resume / inject 是否实装（S9）。"""
    from fastapi.testclient import TestClient

    from lit_agent.api.app import create_app

    app = create_app(settings_for_probe(fresh=True))
    with TestClient(app) as client:
        codes = {}
        for action in ("pause", "resume", "inject"):
            response = client.post(f"/api/runs/none/{action}")
            codes[action] = response.status_code
    implemented = [name for name, code in codes.items() if code != 501]
    return len(implemented) == 3, f"status={codes}"


def probe_retrieval() -> tuple[bool, str]:
    """hybrid 检索工具（S10）。"""
    from lit_agent.tools.registry import Tool, ToolRegistry

    registry = ToolRegistry()
    try:
        registry.register(Tool(name="hybrid_search", run=lambda **_: None))
    except Exception:  # noqa: BLE001 - 只探测能力位
        return False, "registry unavailable"
    return False, "hybrid_search=not implemented"


def probe_eval_suite() -> tuple[bool, str]:
    """judge / faultinject / datasets（S11）。"""
    from lit_agent.errors import FeatureDisabledError

    ok: list[str] = []
    for module_name, attribute in (
        ("lit_agent.eval.judge", "judge_claim"),
        ("lit_agent.eval.faultinject", "inject"),
        ("lit_agent.eval.datasets", "load_gold"),
    ):
        try:
            module = __import__(module_name, fromlist=[attribute])
            func = getattr(module, attribute)
            try:
                func()
            except FeatureDisabledError:
                continue
            except Exception:  # noqa: BLE001
                ok.append(module_name.split(".")[-1])
                continue
        except AttributeError:
            continue
    return len(ok) == 3, f"implemented={ok}"


def probe_web_stages() -> tuple[bool, str]:
    """前端十阶段可视化（S12）。"""
    path = ROOT / "web" / "src" / "components" / "TrajectoryTimeline.vue"
    if not path.exists():
        return False, "TrajectoryTimeline.vue missing"
    text = path.read_text(encoding="utf-8")
    found = sum(1 for stage in EXPECTED_STAGES if f'"{stage}"' in text)
    return found >= len(EXPECTED_STAGES), f"stages_in_ui={found}/{len(EXPECTED_STAGES)}"


def probe_baseline() -> tuple[bool, str]:
    """Phase 1 基线不得回归（必须一直 GREEN）。"""
    script = ROOT / "scripts" / "verify_phase1.py"
    completed = subprocess.run(
        [sys.executable, str(script), "--offline"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    tail = [line for line in (completed.stdout or "").splitlines() if "TOTAL" in line]
    return completed.returncode == 0, tail[-1].strip() if tail else "no TOTAL line"


def probe_tests() -> tuple[bool, str]:
    """后端测试集不得回归（必须一直 GREEN）。"""
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--no-header", "tests/unit", "tests/contract"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(ROOT),
    )
    return completed.returncode == 0, "unit+contract green" if completed.returncode == 0 else "tests failed"


def settings_for_probe(fresh: bool = False) -> Any:
    from lit_agent.config import LoggingSettings, Settings, StorageSettings

    root = Path("D:/lit-agent-store/temp/verify-p2") / ("fresh" if fresh else "probe")
    return Settings(
        storage=StorageSettings(data_root=str(root)),
        logging=LoggingSettings(console=False),
    )


#: (名称, 探针, 目标步骤)
PROBES: tuple[tuple[str, Callable[[], tuple[bool, str]], str], ...] = (
    ("graph.nodes(10)", probe_graph_nodes, "S2"),
    ("graph.edges(E1-E13)", probe_graph_edges, "S3"),
    ("graph.resume", probe_resume, "S4"),
    ("agents.4roles", probe_agents, "S5/S6"),
    ("context.summarize", probe_folding, "S7"),
    ("guards.15", probe_guards, "S8"),
    ("runtime.control", probe_runtime_control, "S9"),
    ("retrieval.hybrid", probe_retrieval, "S10"),
    ("eval.suite", probe_eval_suite, "S11"),
    ("web.10stages", probe_web_stages, "S12"),
    ("baseline.phase1", probe_baseline, "必须 GREEN"),
    ("baseline.tests", probe_tests, "必须 GREEN"),
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Phase 2 capability baseline")
    parser.add_argument("--offline", action="store_true", help="只跑离线探针（默认）")
    parser.add_argument("--online", action="store_true", help="额外跑真实数据回归")
    parser.add_argument("--baseline", action="store_true", help="允许 RED，仅记录基线")
    parser.add_argument("--json", default=None, help="红绿表输出路径")
    args = parser.parse_args(argv)

    report = Report()
    for name, probe, target in PROBES:
        started = time.time()
        try:
            ok, detail = probe()
        except Exception as exc:  # noqa: BLE001 - 探针失败必须记录而不是崩溃
            ok, detail = False, f"{type(exc).__name__}: {str(exc)[:120]}"
        report.add(name, ok, detail, target, time.time() - started)

    if args.online:
        started = time.time()
        script = ROOT / "scripts" / "verify_phase1.py"
        completed = subprocess.run(
            [sys.executable, str(script), "--online"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(ROOT),
        )
        tail = [line for line in (completed.stdout or "").splitlines() if "TOTAL" in line]
        report.add(
            "baseline.phase1_online",
            completed.returncode == 0,
            tail[-1].strip() if tail else "no TOTAL line",
            "必须 GREEN",
            time.time() - started,
        )

    report.emit(Path(args.json) if args.json else None, baseline=args.baseline)
    if args.baseline:
        return 0
    return 0 if report.greens == len(report.results) else 1


if __name__ == "__main__":
    sys.exit(main())

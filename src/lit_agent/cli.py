"""`lit-agent` 单一 CLI 入口（guide §3.1 / phase1 §4）。

设计约束
- **一个入口、可扩展子命令**：未实现的子命令返回退出码 60 + `E_FEATURE_DISABLED`，
  绝不"静默成功"（这是骨架阶段的主要失败模式）；
- 子命令内部**延迟 import**：避免 `lit-agent version` 也加载 kuzu/torch 这类重依赖；
- 所有预期内失败统一走 `LitError`，退出码由错误对象决定。
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

import lit_agent
from lit_agent._version import __version__
from lit_agent.config import load_settings
from lit_agent.errors import (
    EXIT_OK,
    EXIT_USAGE,
    LitError,
    not_implemented,
)

__all__ = ["build_parser", "main"]

REPO_ROOT = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def _usage_error(message: str) -> int:
    print(f"usage error: {message}", file=sys.stderr)
    return EXIT_USAGE


def _json_print(payload: Any) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


# --------------------------------------------------------------------------- #
# handlers: version / doctor
# --------------------------------------------------------------------------- #
def _cmd_version(_args: argparse.Namespace) -> int:
    settings = load_settings()
    print(
        f"lit-agent {__version__} | python {sys.version.split()[0]} "
        f"| sqlite {sqlite3.sqlite_version} | config {settings.config_version}"
    )
    return EXIT_OK


def _cmd_doctor(args: argparse.Namespace) -> int:
    from lit_agent import doctor

    flags: list[str] = []
    if args.strict:
        flags.append("--strict")
    if args.json:
        flags.append("--json")
    return doctor.main(flags)


# --------------------------------------------------------------------------- #
# handlers: db
# --------------------------------------------------------------------------- #
def _cmd_db_upgrade(_args: argparse.Namespace) -> int:
    from lit_agent.db.session import upgrade_database

    settings = load_settings()
    settings.ensure_dirs(strict_ascii=False)
    path = upgrade_database(settings)
    print(f"db upgraded: {path}")
    return EXIT_OK


def _cmd_db_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        return _usage_error("重置会删除本地数据库：确认请加 --yes")
    from lit_agent.db.session import reset_database

    path = reset_database(load_settings())
    print(f"db reset: {path}")
    return EXIT_OK


def _cmd_db_status(_args: argparse.Namespace) -> int:
    from lit_agent.db.session import database_status

    status = database_status(load_settings())
    _json_print(status)
    return EXIT_OK


def _cmd_stores_verify(_args: argparse.Namespace) -> int:
    from lit_agent.stores.rebuild import verify_counts

    report = verify_counts(load_settings())
    _json_print(report)
    return EXIT_OK if report["ok"] else 1


def _cmd_sources_dedup(_args: argparse.Namespace) -> int:
    from lit_agent.sources.dedup import run_dedup

    _json_print(run_dedup(load_settings()))
    return EXIT_OK


def _cmd_sources_project(_args: argparse.Namespace) -> int:
    from lit_agent.sources.dedup import project_citations

    _json_print(project_citations(load_settings()))
    return EXIT_OK


def _cmd_sources_sync(args: argparse.Namespace) -> int:
    from lit_agent.sources.sync import sync_topic

    result = sync_topic(load_settings(), args.topic, limit=args.limit)
    _json_print(result)
    return EXIT_OK


def _cmd_stores_rebuild(args: argparse.Namespace) -> int:
    from lit_agent.stores.rebuild import rebuild_graph, rebuild_vector, verify_counts

    settings = load_settings()
    result: dict[str, Any] = {}
    if args.all or args.graph:
        result["graph"] = rebuild_graph(settings)
    if args.all or args.vector:
        result["vector"] = rebuild_vector(settings)
    if not result:
        return _usage_error("需要 --all / --graph / --vector 之一")
    if args.verify or args.all:
        result["verify"] = verify_counts(settings)
    _json_print(result)
    verify = result.get("verify")
    return EXIT_OK if (verify is None or verify.get("ok")) else 1


def _cmd_run_topic(args: argparse.Namespace) -> int:
    from lit_agent.runtime.budget import RunBudget
    from lit_agent.runtime.runner import run_topic

    settings = load_settings()
    settings.ensure_dirs(strict_ascii=False)
    budget = RunBudget(limit_usd=args.max_usd or settings.routing.run_cost_budget_usd)
    result = run_topic(settings, args.topic, run_id=args.run_id, budget=budget)
    _json_print(result)
    return EXIT_OK if result["state"] == "succeeded" else 1


def _cmd_api_export(args: argparse.Namespace) -> int:
    from lit_agent.api.app import export_openapi

    schema = export_openapi(args.out)
    print(f"openapi written: {args.out} | paths={len(schema.get('paths', {}))}")
    return EXIT_OK


# --------------------------------------------------------------------------- #
# handlers: feature-disabled placeholders（骨架阶段的诚实回执）
# --------------------------------------------------------------------------- #
def _stub(feature: str, step: str):
    def handler(_args: argparse.Namespace) -> int:
        raise not_implemented(feature, f"planned in {step}; see phase1-implementation-steps.md")

    return handler


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lit-agent",
        description="Intelligent multi-agent literature research assistant (Phase 1)",
    )
    parser.add_argument("--version", action="store_true", help="打印版本后退出")
    sub = parser.add_subparsers(dest="command", metavar="<command>")

    p = sub.add_parser("version", help="版本与环境信息")
    p.set_defaults(handler=_cmd_version)

    p = sub.add_parser("doctor", help="六类自检（结构/依赖/配置/路径/存储/版本）")
    p.add_argument("--strict", action="store_true", help="任一项失败即非零退出")
    p.add_argument("--json", action="store_true", help="机器可读输出")
    p.set_defaults(handler=_cmd_doctor)

    db = sub.add_parser("db", help="SQLite 迁移与状态")
    db_sub = db.add_subparsers(dest="db_command", metavar="<action>")
    db_sub.add_parser("upgrade", help="执行 Alembic 迁移到 head").set_defaults(
        handler=_cmd_db_upgrade
    )
    p_reset = db_sub.add_parser("reset", help="删除并重建本地数据库")
    p_reset.add_argument("--yes", action="store_true", help="确认删除")
    p_reset.set_defaults(handler=_cmd_db_reset)
    db_sub.add_parser("status", help="打印 schema/表数/事件数").set_defaults(handler=_cmd_db_status)

    stores = sub.add_parser("stores", help="Kuzu / Qdrant / 文件存储")
    stores_sub = stores.add_subparsers(dest="stores_command", metavar="<action>")
    stores_sub.add_parser("verify", help="三库对账（SQLite vs Kuzu vs Qdrant）").set_defaults(
        handler=_cmd_stores_verify
    )
    p_rebuild = stores_sub.add_parser("rebuild", help="从 SQLite 重建派生物")
    p_rebuild.add_argument("--all", action="store_true")
    p_rebuild.add_argument("--graph", action="store_true")
    p_rebuild.add_argument("--vector", action="store_true")
    p_rebuild.add_argument("--verify", action="store_true")
    p_rebuild.set_defaults(handler=_cmd_stores_rebuild)

    sources = sub.add_parser("sources", help="源适配与增量同步")
    sources_sub = sources.add_subparsers(dest="sources_command", metavar="<action>")
    p_sync = sources_sub.add_parser("sync", help="按 topic selector 增量抓取（Step 1.6）")
    p_sync.add_argument("--topic", required=True)
    p_sync.add_argument("--limit", type=int, default=200)
    p_sync.set_defaults(handler=_cmd_sources_sync)
    sources_sub.add_parser("dedup", help="三段式去重落库（Step 1.8）").set_defaults(
        handler=_cmd_sources_dedup
    )
    sources_sub.add_parser(
        "project", help="把 references 投影成 citations（Step 1.8）"
    ).set_defaults(handler=_cmd_sources_project)

    p = sub.add_parser("run-topic", help="手动触发一次单 topic 运行（Step 1.11）")
    p.add_argument("--topic", required=True)
    p.add_argument("--run-id", default=None)
    p.add_argument("--max-usd", type=float, default=None)
    p.add_argument("--no-cache", action="store_true")
    p.set_defaults(handler=_cmd_run_topic)

    llm = sub.add_parser("llm", help="LLM 网关")
    llm_sub = llm.add_subparsers(dest="llm_command", metavar="<action>")
    p_probe = llm_sub.add_parser("probe", help="真实调用一次并打印 tokens/cost（Step 1.9）")
    p_probe.add_argument("--budget", type=float, default=0.01)
    p_probe.set_defaults(handler=_stub("gateway.llm", "Step 1.9"))

    api = sub.add_parser("api", help="REST / SSE 服务")
    api_sub = api.add_subparsers(dest="api_command", metavar="<action>")
    p_openapi = api_sub.add_parser("export-openapi", help="导出 docs/api/openapi.json（Step 1.15）")
    p_openapi.add_argument("--out", default="docs/api/openapi.json")
    p_openapi.set_defaults(handler=_cmd_api_export)
    p_serve = api_sub.add_parser("serve", help="启动 uvicorn（Step 1.15）")
    p_serve.add_argument("--host", default="127.0.0.1")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.set_defaults(handler=_stub("api.serve", "Step 1.15"))

    ev = sub.add_parser("eval", help="评测与指标")
    ev_sub = ev.add_subparsers(dest="eval_command", metavar="<action>")
    p_metrics = ev_sub.add_parser("metrics", help="从事件算指标（Step 1.18）")
    p_metrics.add_argument("--runs", default="")
    p_metrics.add_argument("--out", default="out/metrics")
    p_metrics.set_defaults(handler=_stub("eval.metrics", "Step 1.18"))

    sch = sub.add_parser("schedule", help="周更调度（Phase 1 仅装配，不注册）")
    sch_sub = sch.add_subparsers(dest="schedule_command", metavar="<action>")
    sch_sub.add_parser("list", help="列出已注册 job（应为空）").set_defaults(
        handler=_stub("runtime.scheduler", "Step 1.17")
    )
    p_once = sch_sub.add_parser("run-once", help="手动跑一次周更 job（等价 run-topic）")
    p_once.add_argument("--topic", required=True)
    p_once.set_defaults(handler=_stub("runtime.scheduler", "Step 1.17"))

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if getattr(args, "version", False):
        return _cmd_version(args)
    handler = getattr(args, "handler", None)
    if handler is None:
        parser.print_help()
        return EXIT_OK
    try:
        return int(handler(args))
    except LitError as exc:
        print(f"{exc.code}: {exc.message}", file=sys.stderr)
        if exc.context:
            print(
                json.dumps(exc.context, ensure_ascii=False, indent=2, default=str), file=sys.stderr
            )
        return exc.exit_code
    except KeyboardInterrupt:  # pragma: no cover - 交互场景
        print("interrupted", file=sys.stderr)
        return 130


def package_version() -> str:
    """供 `--version` 与测试使用。"""
    return lit_agent.__version__


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

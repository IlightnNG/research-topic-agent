"""CLI 入口：`python -m lit_agent_min <command> [options]`。

命令
- `selfcheck`（默认）：配置 / 目录 / 密钥的结构自检，返回退出码 0/2
- `demo-events`：Step 0.2 冒烟——写 3 条事件并回读，验证 seq 单调与 JSONL 形状
- `demo-logging`：Step 0.3 冒烟——同一 run 写事件 + 日志，验证可用 `run_id` 互查
                     并演示脱敏与"ERROR 必带 error_code"契约

扩展约定：后续 Step 的子命令（s1_coverage、s5_walking_skeleton …）也挂在这里，保持单一入口。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import __version__, open_event_log, selfcheck
from .config import ConfigError, load_settings
from .logging import bind_context, clear_context, log_event, setup_logging
from .models import EventType, Severity


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lit_agent_min",
        description="Phase 0 最小内核：自检与工具入口",
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command")

    check = sub.add_parser("selfcheck", help="检查配置、目录与密钥环境（默认命令）")
    check.add_argument("--lax", action="store_true", help="缺少密钥只告警，不返回失败码")
    check.add_argument("--config", default=None, help="指定配置文件路径")

    demo = sub.add_parser("demo-events", help="写 3 条事件并回读（Step 0.2 冒烟）")
    demo.add_argument("--run-id", default=None, help="run 标识（默认 demo-001）")
    demo.add_argument("--out", default=None, help="事件文件路径（默认 <out_dir>/events.jsonl）")

    logdemo = sub.add_parser("demo-logging", help="事件 + 日志关联冒烟（Step 0.3）")
    logdemo.add_argument("--run-id", default=None, help="run 标识（默认按时间生成）")

    return parser


def demo_events(*, run_id: str | None = None, out: str | None = None) -> int:
    """写 3 条 `phase_change` 事件并回读，打印行数与 seq 序列。"""
    try:
        log = open_event_log(Path(out) if out else None, run_id=run_id or "demo-001")
    except ConfigError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2

    for index in range(3):
        log.emit(EventType.PHASE_CHANGE, stage="retrieve", agent="single", payload={"i": index})

    events = log.events()
    print(f"path   {log.path}")
    print(f"lines  {len(events)}")
    print(f"seqs   {[event.seq for event in events]}")
    if events:
        print(f"first  {json.dumps(json.loads(events[0].to_json_line()), ensure_ascii=False)}")
    return 0


def demo_logging(*, run_id: str | None = None) -> int:
    """同一 run 写事件与日志，验证 `run_id` 互查 + 脱敏 + 错误契约。"""
    try:
        settings = load_settings()
        handles = setup_logging(settings)
        rid = run_id or f"p0-log-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        log = open_event_log(settings.paths.out_dir / "events.jsonl", run_id=rid)
    except ConfigError as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 2

    clear_context()
    bind_context(run_id=rid, stage="S2_retrieve", agent="single")

    log_event(Severity.INFO, "phase_enter", "进入检索阶段", logger="lit_agent.demo")
    log.emit(
        EventType.PHASE_CHANGE, stage="S2_retrieve", agent="single", payload={"phase": "enter"}
    )

    log_event(
        Severity.INFO,
        "tool_call_finished",
        "openalex page fetched",
        tool="openalex_search",
        latency_ms=812,
        mailto="zhu@nus.edu.sg",  # 演示脱敏
    )
    log.emit(
        EventType.TOOL_CALL,
        stage="S2_retrieve",
        agent="single",
        payload={"tool": "openalex_search", "ok": True, "latency_ms": 812},
    )

    log_event(
        Severity.ERROR,
        "source_timeout",
        "openalex timeout",
        error_code="E_SRC_TIMEOUT",
        retryable=True,
    )
    log.emit(
        EventType.ERROR,
        stage="S2_retrieve",
        agent="single",
        severity=Severity.ERROR,
        payload={"error_code": "E_SRC_TIMEOUT", "retryable": True},
    )

    events = [event for event in log.events() if event.run_id == rid]
    records = [
        json.loads(line)
        for line in handles.app_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matched = [record for record in records if record.get("run_id") == rid]
    errors = [
        json.loads(line)
        for line in handles.error_log.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    matched_errors = [record for record in errors if record.get("run_id") == rid]

    print(f"run_id      {rid}")
    print(f"events      {len(events)}  ->  {log.path}")
    print(f"log lines   {len(matched)}  ->  {handles.app_log}")
    print(f"error lines {len(matched_errors)}  ->  {handles.error_log}")
    if matched:
        print(f"first log   {json.dumps(matched[0], ensure_ascii=False)}")
    linked = bool(matched) and bool(events) and matched[0]["run_id"] == events[0].run_id
    print(f"[{'OK' if linked else 'FAIL'}] 事件与日志可用 run_id 互相定位")
    clear_context()
    return 0 if linked else 1


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command in (None, "selfcheck"):
        return selfcheck(
            strict=not getattr(args, "lax", False),
            config_path=getattr(args, "config", None),
        )
    if args.command == "demo-events":
        return demo_events(run_id=args.run_id, out=args.out)
    if args.command == "demo-logging":
        return demo_logging(run_id=args.run_id)

    parser.print_help()
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:  # pragma: no cover - 交互中断
        print("interrupted", file=sys.stderr)
        raise SystemExit(130) from None

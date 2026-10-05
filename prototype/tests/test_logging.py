"""Step 0.3 单测：日志基线（字段、脱敏、级别策略、错误分离、查看工具）。

对照验收标准（docs/implementation/phase0-implementation-steps.md §2 Step 0.3）：
1. 日志与事件可用 `run_id` 互相定位（关联字段齐全）；
2. 错误行 100% 带 `error_code`（严格模式直接报错）；
3. 脱敏（密钥 / 邮箱 / 家目录路径 / 长正文）全部生效；
4. `validate_no_bodies()` 可自动扫描 info 行是否混入正文。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from lit_agent_min.config import Logging, Paths, Provider, Providers, Settings
from lit_agent_min.logging import (
    LoggingContractError,
    bind_context,
    clear_context,
    log_event,
    setup_logging,
    validate_no_bodies,
)
from lit_agent_min.models import Severity


def make_settings(tmp_path: Path, **logging_overrides: object) -> Settings:
    logs = tmp_path / "logs"
    logging_cfg = Logging(
        level=logging_overrides.pop("level", "INFO"),
        app_log=logs / "app.jsonl",
        error_log=logs / "errors.jsonl",
        console=logging_overrides.pop("console", False),
        **logging_overrides,  # type: ignore[arg-type]
    )
    return Settings(
        paths=Paths(logs_dir=logs),
        providers=Providers(cloud=Provider(name="deepseek", model="deepseek-chat")),
        logging=logging_cfg,
        config_path=tmp_path / "config.local.yaml",
    )


@pytest.fixture(autouse=True)
def _clean_context() -> None:
    clear_context()
    yield
    clear_context()


def read_records(path: Path) -> list[dict[str, object]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_required_fields_and_context(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    handles = setup_logging(settings, force=True)
    bind_context(run_id="p0-s5-001", topic_id="T1", stage="S2_retrieve", agent="retrieval")

    log_event(Severity.INFO, "demo_started", "事件与日志关联冒烟", logger="lit_agent.demo")

    records = read_records(handles.app_log)
    assert len(records) == 1
    record = records[0]
    for key in (
        "ts",
        "level",
        "event",
        "logger",
        "msg",
        "app_version",
        "config_version",
        "host",
        "pid",
        "schema_version",
    ):
        assert key in record, f"缺少必填字段 {key}"
    assert record["event"] == "demo_started"
    assert record["msg"] == "事件与日志关联冒烟"
    assert record["logger"] == "lit_agent.demo"
    assert record["level"] == "info"
    # 关联字段（与事件表互查的键）
    assert record["run_id"] == "p0-s5-001"
    assert record["stage"] == "S2_retrieve"
    assert record["agent"] == "retrieval"
    assert record["topic_id"] == "T1"
    assert str(record["config_version"]).startswith("cfg-")


def test_masks_secret_email_and_home_path(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    handles = setup_logging(settings, force=True)

    log_event(
        Severity.INFO,
        "source_request",
        "openalex request",
        api_key="sk-live-abcdef123456",
        mailto="zhu@nus.edu.sg",
        pdf_path=str(Path.home() / "papers" / "a.pdf"),
    )

    record = read_records(handles.app_log)[0]
    assert record["api_key"] == "***"
    assert record["mailto"] == "z***@nus.edu.sg"
    # 家目录前缀被替换为 "~"（分隔符跟随平台，断言保持平台无关）
    expected_path = str(Path.home() / "papers" / "a.pdf").replace(str(Path.home()), "~")
    assert record["pdf_path"] == expected_path
    assert str(Path.home()) not in str(record["pdf_path"])


def test_info_body_is_digested_and_passes_scanner(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    handles = setup_logging(settings, force=True)

    long_body = "正文" * 500  # 1000 字符
    log_event(Severity.INFO, "report_drafted", "draft ready", body=long_body)

    record = read_records(handles.app_log)[0]
    assert str(record["body"]).startswith("<redacted chars=1000 sha1=")

    lines = handles.app_log.read_text(encoding="utf-8").splitlines()
    assert validate_no_bodies(lines) == []


def test_validate_no_bodies_detects_violation() -> None:
    bad = json.dumps({"level": "info", "event": "x", "msg": "y" * 600}, ensure_ascii=False)
    assert validate_no_bodies([bad]) != []


def test_error_logged_to_both_files_but_info_only_to_app(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    handles = setup_logging(settings, force=True)

    log_event(Severity.INFO, "phase_enter", "entering retrieve")
    log_event(
        Severity.ERROR,
        "source_timeout",
        "openalex timeout",
        error_code="E_SRC_TIMEOUT",
        retryable=True,
    )

    errors = read_records(handles.error_log)
    assert len(errors) == 1
    assert errors[0]["event"] == "source_timeout"
    assert errors[0]["error_code"] == "E_SRC_TIMEOUT"
    assert errors[0]["retryable"] is True

    app = read_records(handles.app_log)
    assert [record["event"] for record in app] == ["phase_enter", "source_timeout"]


def test_error_without_error_code_raises_in_strict_mode(tmp_path: Path) -> None:
    settings = make_settings(tmp_path)
    setup_logging(settings, force=True)

    with pytest.raises(LoggingContractError) as excinfo:
        log_event(Severity.ERROR, "boom", "something failed")
    assert "error_code" in str(excinfo.value)


def test_error_without_code_allowed_when_not_strict(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, strict_contracts=False)
    handles = setup_logging(settings, force=True)

    log_event(Severity.ERROR, "boom", "something failed")  # 不抛错
    assert read_records(handles.error_log)[0]["event"] == "boom"


def test_event_name_is_required(tmp_path: Path) -> None:
    setup_logging(make_settings(tmp_path), force=True)
    with pytest.raises(LoggingContractError):
        log_event(Severity.INFO, "", "no semantic name")


def test_debug_level_keeps_body_for_local_debugging(tmp_path: Path) -> None:
    settings = make_settings(tmp_path, level="DEBUG")
    handles = setup_logging(settings, force=True)

    long_body = "x" * 800
    log_event(Severity.DEBUG, "prompt_dump", "debug body", body=long_body)

    record = read_records(handles.app_log)[0]
    assert record["body"] == long_body  # DEBUG 允许正文（受控目录）
    lines = handles.app_log.read_text(encoding="utf-8").splitlines()
    assert validate_no_bodies(lines) == []  # 扫描器跳过 debug 行

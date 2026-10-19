"""错误分类学（Step 1.1 验收）。"""

from __future__ import annotations

import pytest

from lit_agent import errors
from lit_agent.errors import (
    EXIT_FEATURE_DISABLED,
    FeatureDisabledError,
    LitError,
    action_for,
    not_implemented,
)


def test_code_must_carry_e_prefix() -> None:
    with pytest.raises(ValueError):
        LitError("NOPE", "bad")


def test_retryable_defaults_come_from_table() -> None:
    assert LitError(errors.E_SRC_TIMEOUT).retryable is True
    assert LitError(errors.E_SRC_4XX).retryable is False
    assert LitError(errors.E_LOCK_HELD).retryable is False
    # 可显式覆盖
    assert LitError(errors.E_SRC_4XX, retryable=True).retryable is True


def test_action_for_uses_longest_prefix() -> None:
    assert action_for(errors.E_DATA_DUP) == "ignore_and_count"
    assert action_for(errors.E_DATA_SYNC) == "rebuild_from_truth"
    assert action_for(errors.E_SRC_RATE) == "backoff_retry"
    assert action_for(errors.E_LOCK_HELD) == "queue_or_reject"
    assert action_for(errors.E_VECTOR_DIM_MISMATCH) == "rebuild_collection"
    assert action_for("E_TOTALLY_UNKNOWN") == "abort_with_report"


def test_error_is_json_friendly() -> None:
    exc = LitError(errors.E_LLM_5XX, "boom", context={"attempt": 2, "run_id": "r1"})
    payload = exc.to_event_payload()
    assert payload["code"] == errors.E_LLM_5XX
    assert payload["retryable"] is True
    assert payload["action_taken"] == "retry_then_degrade"
    # context 的值可能不可序列化，事件里只保留键名
    assert payload["context_keys"] == ["attempt", "run_id"]
    assert "context" not in payload


def test_feature_disabled_is_explicit_and_exit_code_60() -> None:
    exc = FeatureDisabledError("graph.pipeline", "build_graph not implemented yet")
    assert exc.code == errors.E_FEATURE_DISABLED
    assert exc.exit_code == EXIT_FEATURE_DISABLED
    assert exc.feature == "graph.pipeline"
    assert exc.retryable is False
    assert "not implemented yet" in str(exc)
    assert exc.to_event_payload()["context_keys"] == ["feature"]


def test_not_implemented_helper() -> None:
    exc = not_implemented("api.app")
    assert isinstance(exc, FeatureDisabledError)
    assert exc.feature == "api.app"


def test_every_public_code_is_unique_and_prefixed() -> None:
    codes = [
        value
        for name, value in vars(errors).items()
        if name.startswith("E_") and isinstance(value, str)
    ]
    assert len(codes) == len(set(codes)), "错误码不得重复"
    assert all(code.startswith("E_") for code in codes)

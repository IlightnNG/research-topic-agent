"""错误分类学（guide §1.5 + ADR-0003/0004/0005 的补充错误码）。

约定：
- 每个错误对象含 `code / message / retryable / action_taken / context`；
- `code` 是**机器可读契约**：日志、事件、API 错误响应、守卫判决都用它；
- 新增错误码必须归入某个前缀段（`E_<域>_<原因>`），并在 `DEFAULT_ACTION` 里给出默认处置。
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "CODE_RETRYABLE",
    "DEFAULT_ACTION",
    "FeatureDisabledError",
    "LitError",
    "action_for",
    "not_implemented",
]

# --------------------------------------------------------------------------- #
# 进程退出码（CLI 契约）
# --------------------------------------------------------------------------- #
EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_FEATURE_DISABLED = 60

# --------------------------------------------------------------------------- #
# 错误码（九段 + Phase 1 补充段）
# --------------------------------------------------------------------------- #
E_CONFIG_INVALID = "E_CONFIG_INVALID"
E_NOT_FOUND = "E_NOT_FOUND"
E_UNEXPECTED = "E_UNEXPECTED"

E_PROTO_SCHEMA = "E_PROTO_SCHEMA"
E_PROTO_ISERROR = "E_PROTO_ISERROR"

E_SRC_TIMEOUT = "E_SRC_TIMEOUT"
E_SRC_RATE = "E_SRC_RATE"
E_SRC_AUTH = "E_SRC_AUTH"
E_SRC_4XX = "E_SRC_4XX"
E_SRC_5XX = "E_SRC_5XX"
E_SRC_SCHEMA = "E_SRC_SCHEMA"
E_SRC_NO_SELECTOR = "E_SRC_NO_SELECTOR"

E_LLM_TIMEOUT = "E_LLM_TIMEOUT"
E_LLM_RATE = "E_LLM_RATE"
E_LLM_5XX = "E_LLM_5XX"
E_LLM_QUOTA = "E_LLM_QUOTA"
E_LLM_TRUNCATED = "E_LLM_TRUNCATED"

E_SCHEMA_STAGE_OUTPUT = "E_SCHEMA_STAGE_OUTPUT"
E_GROUND_UNRESOLVED_CITATION = "E_GROUND_UNRESOLVED_CITATION"

E_GUARD_DRIFT = "E_GUARD_DRIFT"
E_GUARD_LOOP = "E_GUARD_LOOP"
E_GUARD_STAGNATION = "E_GUARD_STAGNATION"
E_GUARD_TIMEOUT = "E_GUARD_TIMEOUT"
E_GUARD_UNCALIBRATED = "E_GUARD_UNCALIBRATED"

E_BUDGET_TOKENS = "E_BUDGET_TOKENS"
E_BUDGET_TIME = "E_BUDGET_TIME"
E_BUDGET_COST = "E_BUDGET_COST"

E_DATA_DUP = "E_DATA_DUP"
E_DATA_SYNC = "E_DATA_SYNC"
E_DATA_SEQ_CONFLICT = "E_DATA_SEQ_CONFLICT"

E_LOCK_HELD = "E_LOCK_HELD"

E_STORE_NOT_EMPTY = "E_STORE_NOT_EMPTY"
E_STORE_SCHEMA_MISMATCH = "E_STORE_SCHEMA_MISMATCH"
E_STORE_PATH_NONASCII = "E_STORE_PATH_NONASCII"

E_VECTOR_DIM_MISMATCH = "E_VECTOR_DIM_MISMATCH"
E_VECTOR_MODEL_MISMATCH = "E_VECTOR_MODEL_MISMATCH"
E_VECTOR_COLLECTION_MISSING = "E_VECTOR_COLLECTION_MISSING"
E_VECTOR_ENCODE_FAILED = "E_VECTOR_ENCODE_FAILED"

E_POLICY_SENSITIVE = "E_POLICY_SENSITIVE"
E_FEATURE_DISABLED = "E_FEATURE_DISABLED"

#: code → 是否可重试（None = 由错误对象显式给出）
CODE_RETRYABLE: dict[str, bool] = {
    E_SRC_TIMEOUT: True,
    E_SRC_RATE: True,
    E_SRC_AUTH: False,
    E_SRC_5XX: True,
    E_SRC_4XX: False,
    E_SRC_SCHEMA: False,
    E_LLM_TIMEOUT: True,
    E_LLM_RATE: True,
    E_LLM_5XX: True,
    E_LLM_QUOTA: False,
    E_LLM_TRUNCATED: True,
    E_DATA_SEQ_CONFLICT: True,
    E_LOCK_HELD: False,
    E_CONFIG_INVALID: False,
    E_NOT_FOUND: False,
    E_FEATURE_DISABLED: False,
    # F3：补齐全部错误码（此前 24 个靠 `.get(code, False)` 兜底，表本身不完整）
    E_PROTO_ISERROR: True,
    E_PROTO_SCHEMA: True,
    E_SCHEMA_STAGE_OUTPUT: True,
    E_SRC_NO_SELECTOR: False,
    E_GROUND_UNRESOLVED_CITATION: True,
    E_GUARD_DRIFT: True,
    E_GUARD_LOOP: True,
    E_GUARD_STAGNATION: True,
    E_GUARD_TIMEOUT: True,
    E_GUARD_UNCALIBRATED: False,
    E_BUDGET_COST: False,
    E_BUDGET_TOKENS: False,
    E_BUDGET_TIME: False,
    E_POLICY_SENSITIVE: False,
    E_DATA_DUP: False,
    E_DATA_SYNC: True,
    E_STORE_NOT_EMPTY: False,
    E_STORE_PATH_NONASCII: False,
    E_STORE_SCHEMA_MISMATCH: False,
    E_VECTOR_COLLECTION_MISSING: False,
    E_VECTOR_DIM_MISMATCH: False,
    E_VECTOR_ENCODE_FAILED: True,
    E_VECTOR_MODEL_MISMATCH: False,
    E_UNEXPECTED: False,
}

#: 前缀段 → 默认处置（按前缀最长匹配；未命中走 `abort_with_report`）
DEFAULT_ACTION: dict[str, str] = {
    "E_CONFIG_": "fix_config",
    "E_NOT_FOUND": "return_404",
    "E_PROTO_": "reject_and_retry",
    "E_SRC_": "backoff_retry",
    "E_LLM_": "retry_then_degrade",
    "E_SCHEMA_": "retry_once_then_degrade",
    "E_GROUND_": "mark_and_rewrite",
    "E_GUARD_": "conditional_edge_backoff",
    "E_BUDGET_": "degrade_or_abort",
    "E_DATA_DUP": "ignore_and_count",
    "E_DATA_SYNC": "rebuild_from_truth",
    "E_DATA_": "idempotent_replay",
    "E_LOCK_": "queue_or_reject",
    "E_STORE_": "reset_or_fix_path",
    "E_VECTOR_": "rebuild_collection",
    "E_POLICY_": "block_zero_egress",
    "E_FEATURE_": "reject_not_implemented",
    "E_UNEXPECTED": "abort_with_report",
}


def action_for(code: str) -> str:
    """按最长前缀匹配返回默认处置。"""
    best = ""
    for prefix in DEFAULT_ACTION:
        if code.startswith(prefix) and len(prefix) > len(best):
            best = prefix
    return DEFAULT_ACTION.get(best, "abort_with_report")


class LitError(Exception):
    """项目内所有**预期内**失败的载体（禁止用裸 Exception 表达可分类失败）。"""

    def __init__(
        self,
        code: str,
        message: str = "",
        *,
        retryable: bool | None = None,
        action_taken: str | None = None,
        context: dict[str, Any] | None = None,
        exit_code: int = EXIT_ERROR,
    ) -> None:
        if not code or not code.startswith("E_"):
            raise ValueError(f"错误码必须是 E_ 前缀（收到 {code!r}）")
        self.code = code
        self.message = message
        self.retryable = CODE_RETRYABLE.get(code, False) if retryable is None else retryable
        self.action_taken = action_taken or action_for(code)
        self.context: dict[str, Any] = dict(context or {})
        self.exit_code = exit_code
        super().__init__(f"{code}: {message}" if message else code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "retryable": self.retryable,
            "action_taken": self.action_taken,
            "context": self.context,
        }

    def to_event_payload(self) -> dict[str, Any]:
        """事件 `payload` 的最小形态（不能塞入不可序列化对象）。"""
        payload = self.to_dict()
        payload.pop("context", None)
        payload["context_keys"] = sorted(self.context)
        return payload


class FeatureDisabledError(LitError):
    """骨架阶段的**显式未实现**：缺逻辑必须抛它，禁止返回空值冒充完成。"""

    def __init__(self, feature: str, detail: str = "") -> None:
        message = f"feature '{feature}' is not implemented yet"
        if detail:
            message = f"{message}: {detail}"
        super().__init__(
            E_FEATURE_DISABLED,
            message,
            retryable=False,
            action_taken="reject_not_implemented",
            context={"feature": feature},
            exit_code=EXIT_FEATURE_DISABLED,
        )
        self.feature = feature


def not_implemented(feature: str, detail: str = "") -> FeatureDisabledError:
    """构造一个 `FeatureDisabledError`（供 `raise not_implemented(...)` 使用）。"""
    return FeatureDisabledError(feature, detail)

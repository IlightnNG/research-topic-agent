"""LLM 网关单测（不触网：注入假 completer）。

重点覆盖 S5 实测踩到/必须防住的坑
- **截断**（reasoning 模型把 max_tokens 吃光 → content 为空、finish_reason=length）必须被识别并重试；
- 缓存命中时**不重复计费**、且复用同一结果（重跑确定性）；
- 预算熔断；
- JSON 围栏与解析。
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from lit_agent_min.llm import LLMBudgetExceeded, LLMError, LLMGateway


class FakeCompleter:
    """按脚本返回响应；记录调用次数与参数。"""

    def __init__(self, scripts: list[dict]) -> None:
        self.scripts = list(scripts)
        self.calls: list[dict] = []

    def __call__(self, **kwargs):
        self.calls.append(kwargs)
        script = (
            self.scripts.pop(0) if self.scripts else {"content": '{"ok":true}', "finish": "stop"}
        )
        return _response(
            script.get("content", ""),
            finish=script.get("finish", "stop"),
            prompt_tokens=script.get("prompt_tokens", 10),
            completion_tokens=script.get("completion_tokens", 5),
            reasoning=script.get("reasoning", ""),
        )


def _response(
    content: str, *, finish: str, prompt_tokens: int, completion_tokens: int, reasoning: str
):
    message = SimpleNamespace(content=content, reasoning_content=reasoning)
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish)],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
        model="deepseek-flash",
    )


def _gateway(tmp_path: Path, completer, **kwargs) -> LLMGateway:
    return LLMGateway(
        model="deepseek/deepseek-flash",
        cache_dir=tmp_path / "cache",
        completer=completer,
        max_attempts=kwargs.pop("max_attempts", 3),
        **kwargs,
    )


def test_json_mode_parses_object_and_records_usage(tmp_path: Path) -> None:
    completer = FakeCompleter(
        [{"content": '{"cards": []}', "prompt_tokens": 120, "completion_tokens": 30}]
    )
    gw = _gateway(tmp_path, completer)
    call = gw.chat_json([{"role": "user", "content": "hi"}], task="t")
    assert call.data == {"cards": []}
    assert call.usage.prompt_tokens == 120
    assert call.cached is False
    assert gw.summary()["network_calls"] == 1


def test_truncated_output_is_retried_with_larger_budget(tmp_path: Path) -> None:
    """第一次 length（reasoning 吃光预算）→ 必须重试，而不是把空内容当成功。"""
    completer = FakeCompleter(
        [
            {"content": "", "finish": "length", "reasoning": "thinking…", "completion_tokens": 16},
            {"content": '{"ok": true}', "finish": "stop", "completion_tokens": 40},
        ]
    )
    gw = _gateway(tmp_path, completer)
    call = gw.chat_json([{"role": "user", "content": "hi"}], task="t", max_tokens=16)
    assert call.data == {"ok": True}
    assert call.attempts == 2
    assert gw.summary()["retries"] == 1
    # 第二次调用的预算被放大
    assert completer.calls[1]["max_tokens"] > completer.calls[0]["max_tokens"]


def test_empty_content_with_stop_finish_counts_as_failure(tmp_path: Path) -> None:
    """空正文（即使 finish_reason 不是 length）也必须判失败：重试耗尽后抛 `LLMError`。"""
    completer = FakeCompleter([{"content": "   ", "finish": "stop"}] * 3)
    gw = _gateway(tmp_path, completer, max_attempts=2)
    with pytest.raises(LLMError):
        gw.chat_json([{"role": "user", "content": "hi"}], task="t")
    assert len(completer.calls) == 2  # 重试到上限


def test_cache_hit_does_not_recharge_and_reuses_result(tmp_path: Path) -> None:
    completer = FakeCompleter(
        [{"content": '{"v": 1}', "prompt_tokens": 50, "completion_tokens": 10}]
    )
    gw = _gateway(tmp_path, completer)
    first = gw.chat_json([{"role": "user", "content": "same"}], task="t")
    second = gw.chat_json([{"role": "user", "content": "same"}], task="t")
    assert len(completer.calls) == 1  # 第二次没有触网
    assert second.cached is True
    assert second.data == first.data == {"v": 1}
    summary = gw.summary()
    assert summary["cache_hits"] == 1
    assert summary["network_calls"] == 1
    assert summary["avoided_tokens_by_cache"] > 0


def test_cache_disabled_forces_network(tmp_path: Path) -> None:
    completer = FakeCompleter([{"content": '{"v": 1}'}, {"content": '{"v": 1}'}])
    gw = _gateway(tmp_path, completer, use_cache=False)
    gw.chat_json([{"role": "user", "content": "same"}], task="t")
    gw.chat_json([{"role": "user", "content": "same"}], task="t")
    assert len(completer.calls) == 2


def test_budget_guard_blocks_further_calls(tmp_path: Path) -> None:
    """预算熔断：成本已超预算时后续调用必须被直接拒绝（且不发起请求）。

    假 completer 无法产出 litellm 价格，故直接设置累计成本来验证熔断逻辑本身。
    """
    completer = FakeCompleter([{"content": '{"v": 1}'}])
    gw = _gateway(tmp_path, completer, budget_usd=1.0, use_cache=False)
    gw.totals.cost_usd = 5.0  # 模拟此前已花费 $5 > 预算 $1
    with pytest.raises(LLMBudgetExceeded):
        gw.chat_json([{"role": "user", "content": "a"}], task="t")
    assert completer.calls == []  # 熔断发生在调用之前


def test_json_fence_is_stripped(tmp_path: Path) -> None:
    completer = FakeCompleter([{"content": '```json\n{"v": 2}\n```'}])
    gw = _gateway(tmp_path, completer)
    assert gw.chat_json([{"role": "user", "content": "hi"}], task="t").data == {"v": 2}


def test_non_json_text_returns_none_data(tmp_path: Path) -> None:
    completer = FakeCompleter([{"content": "plain text answer"}])
    gw = _gateway(tmp_path, completer)
    call = gw.chat_json([{"role": "user", "content": "hi"}], task="t")
    assert call.data is None
    assert call.text == "plain text answer"


def test_cache_file_is_written_as_json(tmp_path: Path) -> None:
    completer = FakeCompleter([{"content": '{"v": 3}'}])
    gw = _gateway(tmp_path, completer)
    call = gw.chat_json([{"role": "user", "content": "hi"}], task="t")
    cached = json.loads((tmp_path / "cache" / f"{call.cache_key}.json").read_text(encoding="utf-8"))
    assert cached["data"] == {"v": 3}
    assert "v" in cached["text"]

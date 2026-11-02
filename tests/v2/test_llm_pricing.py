"""Pricing calculation smoke test."""

from __future__ import annotations

from lit_agent_v2.kernel.llm import DeepSeekChatClient, LLMConfig


def test_deepseek_flash_usage_cost() -> None:
    config = LLMConfig(
        base_url="https://api.deepseek.com",
        model="deepseek-flash",
        api_key="test",
        input_cost_per_m=1.0,
        output_cost_per_m=2.0,
        off_peak_multiplier=0.5,
    )
    usage = DeepSeekChatClient(config)._usage(
        {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000},
        "test",
    )
    assert usage.prompt_tokens == 1_000_000
    assert usage.completion_tokens == 1_000_000
    assert 1.5 <= usage.cost_usd <= 3.0

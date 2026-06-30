from __future__ import annotations

import asyncio

from services.benchmarks.ai_gateway_mock import format_result, run_benchmark


def test_ai_gateway_mock_benchmark_openai_compat():
    result = asyncio.run(run_benchmark("openai_compat", target_events=32, batch_size=8, timeout_seconds=4))
    assert result.events == 32
    assert result.batches == 4
    assert result.batch_size == 8
    assert result.events_per_second > 0
    output = format_result(result)
    assert "provider=openai_compat" in output
    assert "avg_prompt_bytes=" in output


def test_ai_gateway_mock_benchmark_ollama():
    result = asyncio.run(run_benchmark("ollama", target_events=16, batch_size=4, timeout_seconds=4))
    assert result.events == 16
    assert result.batches == 4
    assert result.events_per_second > 0

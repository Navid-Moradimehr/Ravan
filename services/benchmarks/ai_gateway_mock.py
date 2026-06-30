from __future__ import annotations

import argparse
import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any

import httpx

from services.ai_gateway.config import Settings
from services.ai_gateway.providers import LLMProviderClient, build_industrial_prompt


@dataclass(frozen=True)
class BenchmarkResult:
    provider: str
    events: int
    batches: int
    batch_size: int
    elapsed_seconds: float
    events_per_second: float
    batches_per_second: float
    avg_prompt_bytes: float
    avg_summary_bytes: float


def _realistic_event(device_index: int, reading_index: int) -> dict[str, Any]:
    base_temperature = 48.0 + (device_index % 7) * 2.4
    base_vibration = 1.2 + (device_index % 5) * 0.35
    base_pressure = 6.2 + (device_index % 6) * 0.28
    drift = (reading_index % 9) * 0.42
    severity = "critical" if drift > 2.8 else "warning" if drift > 1.6 else "normal"
    return {
        "event_id": f"evt-{reading_index:06d}",
        "source_protocol": ["mqtt", "opcua", "modbus"][device_index % 3],
        "source_id": f"site-a/line-{(device_index % 4) + 1}/asset-{device_index:03d}",
        "asset_id": f"Pump-{device_index:03d}",
        "tag": ["Temperature", "Vibration", "Pressure"][device_index % 3],
        "value": round((base_temperature if device_index % 3 == 0 else base_vibration if device_index % 3 == 1 else base_pressure) + drift, 2),
        "quality": "good",
        "unit": ["c", "mm/s", "bar"][device_index % 3],
        "site": "Plant-01",
        "line": f"Line-{(device_index % 4) + 1}",
        "device_id": f"Pump-{device_index:03d}",
        "severity": severity,
        "ts_source": f"2026-06-27T08:{reading_index % 60:02d}:{reading_index % 60:02d}Z",
    }


def _build_batches(target_events: int, batch_size: int) -> list[list[dict[str, Any]]]:
    batches: list[list[dict[str, Any]]] = []
    reading_index = 0
    device_count = max(8, batch_size // 2)
    while reading_index < target_events:
        batch: list[dict[str, Any]] = []
        for i in range(batch_size):
            if reading_index >= target_events:
                break
            batch.append(_realistic_event(i % device_count, reading_index))
            reading_index += 1
        batches.append(batch)
    return batches


def _build_transport(provider: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        content = json.dumps({"choices": [{"message": {"content": '{"mode":"mock","status":"ok"}'}}]})
        if provider == "ollama":
            content = json.dumps({"message": {"content": '{"mode":"mock","status":"ok"}'}})
        return httpx.Response(200, json=json.loads(content))

    return httpx.MockTransport(handler)


async def run_benchmark(provider: str, target_events: int, batch_size: int, timeout_seconds: int) -> BenchmarkResult:
    settings = Settings(
        llm_provider=provider,
        llm_endpoint_url="http://mock-llm.local/v1" if provider != "ollama" else "http://mock-ollama.local",
        llm_model_id="mistral-small",
        llm_api_key="mock-key",
    )
    client = LLMProviderClient(settings)
    batches = _build_batches(target_events, batch_size)
    summary_sizes: list[int] = []
    prompt_sizes: list[int] = []
    transport = _build_transport(provider)

    started = time.perf_counter()
    async with httpx.AsyncClient(transport=transport, timeout=timeout_seconds) as http_client:
        for batch in batches:
            prompt = build_industrial_prompt(batch)
            prompt_sizes.append(len(prompt.encode("utf-8")))
            content = await client.summarize(prompt, timeout_seconds, client=http_client)
            summary_sizes.append(len(content.encode("utf-8")))
    elapsed = time.perf_counter() - started
    events = sum(len(batch) for batch in batches)
    batches_count = len(batches)
    return BenchmarkResult(
        provider=provider,
        events=events,
        batches=batches_count,
        batch_size=batch_size,
        elapsed_seconds=elapsed,
        events_per_second=events / elapsed if elapsed > 0 else 0.0,
        batches_per_second=batches_count / elapsed if elapsed > 0 else 0.0,
        avg_prompt_bytes=statistics.mean(prompt_sizes) if prompt_sizes else 0.0,
        avg_summary_bytes=statistics.mean(summary_sizes) if summary_sizes else 0.0,
    )


def format_result(result: BenchmarkResult) -> str:
    return "\n".join(
        [
            f"provider={result.provider}",
            f"events={result.events}",
            f"batches={result.batches}",
            f"batch_size={result.batch_size}",
            f"elapsed_seconds={result.elapsed_seconds:.4f}",
            f"events_per_second={result.events_per_second:.2f}",
            f"batches_per_second={result.batches_per_second:.2f}",
            f"avg_prompt_bytes={result.avg_prompt_bytes:.1f}",
            f"avg_summary_bytes={result.avg_summary_bytes:.1f}",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark the AI gateway provider abstraction with realistic mock batches.")
    parser.add_argument("--provider", default="openai_compat", choices=["openai_compat", "vllm", "tgi", "ollama", "llama_cpp", "triton", "custom_http"])
    parser.add_argument("--events", type=int, default=10000)
    parser.add_argument("--batch-size", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=int, default=8)
    args = parser.parse_args()
    result = asyncio.run(run_benchmark(args.provider, args.events, args.batch_size, args.timeout_seconds))
    print(format_result(result))


if __name__ == "__main__":
    main()

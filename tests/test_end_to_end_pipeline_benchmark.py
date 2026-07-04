from __future__ import annotations

from pathlib import Path

from services.benchmarks.end_to_end_pipeline import format_result, run_benchmark


def test_end_to_end_pipeline_msgpack_uses_smaller_payloads() -> None:
    csv_path = Path("data/benchmarks/industrial_mixed_benchmark.csv")

    json_result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0, wire_format="json")
    msgpack_result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0, wire_format="msgpack")

    assert json_result.events == 20
    assert msgpack_result.events == 20
    assert msgpack_result.payload_bytes <= json_result.payload_bytes
    assert msgpack_result.roundtrip_bytes <= json_result.roundtrip_bytes
    assert "wire_format=msgpack" in format_result(msgpack_result)

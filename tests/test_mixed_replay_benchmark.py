from __future__ import annotations

from pathlib import Path

from services.benchmarks.mixed_replay import format_result, run_benchmark


def test_run_benchmark_on_small_csv() -> None:
    csv_path = Path("data/benchmarks/industrial_mixed_benchmark.csv")

    result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0)

    assert result.events == 20
    assert result.invalid_events == 0
    assert result.batches == 5
    assert result.events_per_second > 0
    assert "events_per_second" in format_result(result)

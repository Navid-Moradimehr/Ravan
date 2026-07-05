from __future__ import annotations

from pathlib import Path

from services.benchmarks.real_world_simulator import format_result, run_suite


def test_run_real_world_simulator_suite() -> None:
    baseline_csv = Path("data/benchmarks/industrial_mixed_benchmark.csv")

    result = run_suite(
        baseline_csv=baseline_csv,
        events=20,
        batch_size=4,
        warmup_events=0,
        cases=[
            "mock-normal",
            "mock-drift",
            "mock-spike",
            "swat",
            "multi-plc-line",
            "burst-load",
            "dropout-reconnect",
            "multi-site-correlation",
            "industrial-benchmark",
        ],
    )

    assert len(result.cases) == 9
    assert result.average_events_per_second > 0
    assert result.cases[0].events == 20
    assert "mock-normal" in format_result(result)
    assert "mock-spike" in format_result(result)
    assert "swat" in format_result(result)
    assert "multi-plc-line" in format_result(result)
    assert "dropout-reconnect" in format_result(result)
    assert "multi-site-correlation" in format_result(result)

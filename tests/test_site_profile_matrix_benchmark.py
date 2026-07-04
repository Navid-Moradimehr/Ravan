from __future__ import annotations

from pathlib import Path

from services.benchmarks.site_profile_matrix import format_result, run_matrix


def test_run_site_profile_matrix() -> None:
    csv_path = Path("data/benchmarks/industrial_mixed_benchmark.csv")

    result = run_matrix(
        Path("config/project-manifest.yaml"),
        csv_path,
        site_ids=["demo-site", "plant-a"],
        events=20,
        batch_size=4,
        warmup_events=0,
        min_average_events_per_second=1.0,
        repeat_count=2,
    )

    assert result.passed is True
    assert len(result.runs) == 2
    assert all(run.passed for run in result.runs)
    assert all(run.repeat_count == 2 for run in result.runs)
    assert all(run.median_events_per_second >= 0 for run in result.runs)
    assert "demo-site" in format_result(result)
    assert "median" in format_result(result)

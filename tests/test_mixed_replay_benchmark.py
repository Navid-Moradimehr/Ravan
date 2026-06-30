from __future__ import annotations

import csv
from pathlib import Path

from services.benchmarks.mixed_replay import format_result, run_benchmark


def test_run_benchmark_on_small_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "mixed.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "event_id",
                "source_protocol",
                "source_id",
                "asset_id",
                "tag",
                "value",
                "quality",
                "unit",
                "site",
                "line",
                "ts_source",
                "schema_version",
                "fault_type",
                "scenario_id",
                "ground_truth_severity",
                "step",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "event_id": "evt-1",
                "source_protocol": "mqtt",
                "source_id": "factory/line-1/pump-01/Temperature",
                "asset_id": "Pump-01",
                "tag": "Temperature",
                "value": "55.1",
                "quality": "good",
                "unit": "c",
                "site": "Factory-A",
                "line": "Line-1",
                "ts_source": "2026-06-27T08:00:00Z",
                "schema_version": "1",
                "fault_type": "normal",
                "scenario_id": "bmk-normal",
                "ground_truth_severity": "normal",
                "step": "0",
            }
        )
        writer.writerow(
            {
                "event_id": "evt-2",
                "source_protocol": "opcua",
                "source_id": "ns=2;s=Pump-02.Vibration",
                "asset_id": "Pump-02",
                "tag": "Vibration",
                "value": "7.5",
                "quality": "good",
                "unit": "mm/s",
                "site": "Factory-A",
                "line": "Line-2",
                "ts_source": "2026-06-27T08:00:01Z",
                "schema_version": "1",
                "fault_type": "degradation",
                "scenario_id": "bmk-degrade",
                "ground_truth_severity": "critical",
                "step": "1",
            }
        )

    result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0)

    assert result.events == 20
    assert result.invalid_events == 0
    assert result.batches == 5
    assert result.events_per_second > 0
    assert "events_per_second" in format_result(result)

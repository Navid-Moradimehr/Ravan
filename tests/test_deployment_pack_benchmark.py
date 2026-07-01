from __future__ import annotations

import csv
from pathlib import Path

from services.benchmarks.deployment_pack import format_result, run_benchmark

REPO_ROOT = Path(__file__).resolve().parents[1]
MANIFEST = REPO_ROOT / "config" / "project-manifest.yaml"


def _write_mock_csv(csv_path: Path) -> None:
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
        for idx, protocol in enumerate(("mqtt", "opcua", "modbus")):
            writer.writerow(
                {
                    "event_id": f"evt-{idx}",
                    "source_protocol": protocol,
                    "source_id": f"site-a/{protocol}/pump-{idx}",
                    "asset_id": f"Pump-{idx}",
                    "tag": "Temperature" if idx == 0 else "Vibration",
                    "value": str(50 + idx * 2),
                    "quality": "good",
                    "unit": "c" if idx == 0 else "mm/s",
                    "site": "Factory-A",
                    "line": "Line-1",
                    "ts_source": f"2026-07-01T00:00:0{idx}Z",
                    "schema_version": "1",
                    "fault_type": "normal" if idx == 0 else "degradation",
                    "scenario_id": "mock-benchmark",
                    "ground_truth_severity": "normal",
                    "step": str(idx),
                }
            )


def test_run_deployment_pack_benchmark(tmp_path: Path) -> None:
    csv_path = tmp_path / "mock.csv"
    _write_mock_csv(csv_path)

    result = run_benchmark(
        MANIFEST,
        csv_path,
        site_id="demo-site",
        target_events=24,
        batch_size=6,
        warmup_events=0,
    )

    assert result.export_file_count > 0
    assert result.systemd_file_count >= 4
    assert result.kubernetes_file_count >= 7
    assert result.replay_events == 24
    assert result.replay_events_per_second > 0
    assert result.replay_batches > 0
    assert "export_file_count" in format_result(result)


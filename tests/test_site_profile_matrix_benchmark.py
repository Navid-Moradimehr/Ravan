from __future__ import annotations

from pathlib import Path

from services.benchmarks.site_profile_matrix import format_result, run_matrix


def test_run_site_profile_matrix(tmp_path: Path) -> None:
    csv_path = tmp_path / "baseline.csv"
    csv_path.write_text(
        "\n".join(
            [
                "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                "evt-2,opcua,site-a/opcua/pump-2,Pump-2,Vibration,7.5,good,mm/s,Factory-A,Line-1,2026-07-01T00:00:01Z,1,degradation,mock-benchmark,normal,1",
            ]
        ),
        encoding="utf-8",
    )

    result = run_matrix(
        Path("config/project-manifest.yaml"),
        csv_path,
        site_ids=["demo-site", "plant-a"],
        events=20,
        batch_size=4,
        warmup_events=0,
        min_average_events_per_second=1.0,
    )

    assert result.passed is True
    assert len(result.runs) == 2
    assert all(run.passed for run in result.runs)
    assert "demo-site" in format_result(result)

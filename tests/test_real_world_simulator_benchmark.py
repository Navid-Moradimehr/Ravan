from __future__ import annotations

from pathlib import Path

from services.benchmarks.real_world_simulator import format_result, run_suite


def test_run_real_world_simulator_suite(tmp_path: Path) -> None:
    baseline_csv = tmp_path / "baseline.csv"
    baseline_csv.write_text(
        "\n".join(
            [
                "event_id,source_protocol,source_id,asset_id,tag,value,quality,unit,site,line,ts_source,schema_version,fault_type,scenario_id,ground_truth_severity,step",
                "evt-1,mqtt,site-a/mqtt/pump-1,Pump-1,Temperature,55.1,good,c,Factory-A,Line-1,2026-07-01T00:00:00Z,1,normal,mock-benchmark,normal,0",
                "evt-2,opcua,site-a/opcua/pump-2,Pump-2,Vibration,7.5,good,mm/s,Factory-A,Line-1,2026-07-01T00:00:01Z,1,degradation,mock-benchmark,normal,1",
            ]
        ),
        encoding="utf-8",
    )

    result = run_suite(
        baseline_csv=baseline_csv,
        events=20,
        batch_size=4,
        warmup_events=0,
        cases=["mock-normal", "multi-plc-line", "burst-load", "dropout-reconnect", "industrial-benchmark"],
    )

    assert len(result.cases) == 5
    assert result.average_events_per_second > 0
    assert result.cases[0].events == 20
    assert "mock-normal" in format_result(result)
    assert "multi-plc-line" in format_result(result)
    assert "dropout-reconnect" in format_result(result)

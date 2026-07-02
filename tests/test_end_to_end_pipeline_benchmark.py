from __future__ import annotations

from pathlib import Path

from services.benchmarks.end_to_end_pipeline import format_result, run_benchmark


def test_end_to_end_pipeline_msgpack_uses_smaller_payloads(tmp_path: Path) -> None:
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

    json_result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0, wire_format="json")
    msgpack_result = run_benchmark(csv_path, target_events=20, batch_size=4, warmup_events=0, wire_format="msgpack")

    assert json_result.events == 20
    assert msgpack_result.events == 20
    assert msgpack_result.payload_bytes <= json_result.payload_bytes
    assert msgpack_result.roundtrip_bytes <= json_result.roundtrip_bytes
    assert "wire_format=msgpack" in format_result(msgpack_result)


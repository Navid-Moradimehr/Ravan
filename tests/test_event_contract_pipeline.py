from services.common.normalize import normalize_runtime_event
from services.common.runtime_event import RuntimeEventRecord
from services.edge_ingest.model import IndustrialEvent, validate_event
from services.processor.runtime_pipeline import build_runtime_event_payload


def test_canonical_event_context_survives_normalize_and_enrich():
    payload = {
        "event_id": "contract-1",
        "source_protocol": "opcua",
        "source_id": "site-a/opcua/plc-1",
        "asset_id": "pump-1",
        "tag": "Temperature",
        "value": 66.5,
        "quality": "good",
        "unit": "c",
        "site": "site-a",
        "line": "line-1",
        "ts_source": "2026-01-01T00:00:00+00:00",
        "source_connection_id": "opcua-connection-1",
        "source_config_version": 4,
        "mapping_version": "mapping-7",
        "lineage_id": "lineage-1",
    }
    event, dead_letter = validate_event(payload)
    assert dead_letter is None
    assert isinstance(event, IndustrialEvent)

    normalized = normalize_runtime_event(event)
    assert normalized["event_id"] == "contract-1"
    assert normalized["site_id"] == "site-a"
    assert normalized["timestamp"] == payload["ts_source"]
    assert normalized["unit"] == "c"

    runtime = RuntimeEventRecord.from_raw_mapping(payload)
    enriched = build_runtime_event_payload(runtime, temperature_avg_c=66.5, vibration_avg_mm_s=0, window_size=5)
    for field in ("event_id", "source_id", "asset_id", "tag", "site_id", "timestamp", "lineage_id"):
        assert enriched[field] == runtime.to_dict()[field]
    assert enriched["anomaly_score"] >= 0
    assert enriched["severity"] in {"normal", "warning", "critical"}

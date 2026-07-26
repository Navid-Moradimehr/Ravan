from __future__ import annotations

import json

import pytest


def _event() -> dict[str, object]:
    return {"event_id": "evt-1", "source_id": "sensor-1", "site_id": "plant-a", "schema_version": 1, "value": 12.5}


def test_federation_envelope_preserves_origin_and_payload():
    from services.common.federation_contract import deduplication_key, unwrap_event, validate_envelope, wrap_event

    envelope = wrap_event(_event(), site_id="plant-a", deployment_id="edge-a", topic="industrial.normalized", processing_version="processor-7")
    assert validate_envelope(envelope) == []
    payload, metadata = unwrap_event(envelope)
    assert payload == _event()
    assert metadata["deployment_id"] == "edge-a"
    assert deduplication_key(envelope) == "plant-a|sensor-1|industrial.normalized|evt-1"


def test_federation_rejects_mismatched_payload_identity():
    from services.common.federation_contract import FederationContractError, unwrap_event, wrap_event

    envelope = wrap_event(_event(), site_id="plant-a", deployment_id="edge-a", topic="industrial.normalized")
    envelope["payload"]["event_id"] = "evt-other"
    with pytest.raises(FederationContractError, match="does not match"):
        unwrap_event(envelope)


def test_delivery_ledger_is_durable_and_retries_failed_claim(tmp_path):
    from services.federation.delivery_ledger import DeliveryLedger

    ledger = DeliveryLedger(tmp_path / "ledger.json", max_records=2)
    assert ledger.claim("one")
    ledger.record("one", status="succeeded")
    assert not ledger.claim("one")
    assert ledger.claim("two")
    ledger.record("two", status="failed", metadata={"error": "sink unavailable"})
    assert ledger.claim("two")
    ledger.record("two", status="succeeded")
    assert ledger.claim("three")
    assert ledger.snapshot()["count"] == 2


def test_bridge_decoder_accepts_legacy_and_marks_it():
    from services.federation.kafka_lakehouse_bridge import decode_forwarded_message

    event, metadata, _ = decode_forwarded_message(json.dumps(_event()).encode(), topic="local.industrial.normalized")
    assert metadata["legacy"] is True
    assert event["federation_legacy"] is True


def test_federation_delivery_metric_helper_is_safe():
    from services.common.runtime_metrics import observe_federation_delivery

    observe_federation_delivery("industrial.normalized", "duplicate", 2)

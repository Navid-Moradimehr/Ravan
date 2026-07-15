from __future__ import annotations

import pytest

from services.common.model_data_contract import ObservationArtifactReference
from services.common.operational_event import OperationalEvent
from services.edge_ingest.model import IndustrialEvent


def test_legacy_industrial_event_remains_valid() -> None:
    event = IndustrialEvent(
        source_protocol="mqtt",
        source_id="sensor-1",
        asset_id="pump-1",
        tag="temperature",
        value=42.0,
        ts_source="2026-01-01T00:00:00Z",
    )
    assert event.schema_version == 1
    assert event.sequence_number is None


def test_v2_event_preserves_clock_and_context_evidence() -> None:
    event = IndustrialEvent(
        source_protocol="opcua",
        source_id="plc-1",
        asset_id="pump-1",
        tag="pressure",
        value=4.2,
        ts_source="2026-01-01T00:00:00Z",
        schema_version=2,
        sequence_number=7,
        clock_id="plc-1-clock",
        clock_sync_status="synchronized",
        timestamp_uncertainty_ms=1.5,
        calibration_version="cal-3",
        topology_version="topology-2",
        context_id="batch-9",
    )
    assert event.sequence_number == 7
    assert event.topology_version == "topology-2"


def test_artifact_reference_requires_allowed_uri_and_checksum() -> None:
    artifact = ObservationArtifactReference(
        artifact_id="wave-1",
        site_id="plant-a",
        source_id="accelerometer-1",
        modality="waveform",
        uri="s3://factory/wave-1.bin",
        sha256="a" * 64,
        sample_rate_hz=16000,
    )
    assert artifact.sha256 == "a" * 64
    with pytest.raises(ValueError, match="allowed"):
        ObservationArtifactReference(
            artifact_id="bad",
            site_id="plant-a",
            source_id="sensor",
            modality="image",
            uri="https://example.invalid/image.jpg",
        )


def test_declared_action_payload_is_validated() -> None:
    event = OperationalEvent(
        event_type="control.command.applied",
        event_kind="action",
        schema_ref="industrial.action.v1",
        source_id="plc-audit",
        site_id="plant-a",
        payload={
            "action_id": "action-1",
            "command": "speed_setpoint",
            "requested_value": 42,
            "applied_value": 40,
            "status": "applied",
        },
    )
    assert event.payload["action_id"] == "action-1"


def test_custom_operational_payload_remains_supported() -> None:
    event = OperationalEvent(
        event_type="company.custom.context",
        event_kind="context",
        source_id="mes",
        payload={"recipe": "R-42", "operator_note": "changeover"},
    )
    assert event.payload["recipe"] == "R-42"

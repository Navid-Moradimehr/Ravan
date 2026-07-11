from __future__ import annotations

from services.common.operational_event import OperationalEvent


def test_operational_event_is_domain_neutral() -> None:
    event = OperationalEvent(
        event_type="control.command.applied",
        event_kind="action",
        source_id="plc-audit",
        site_id="plant-a",
        entity_id="pump-01",
        correlation_id="batch-42",
        payload={"command": "speed_setpoint", "requested": 42, "applied": 40},
    )
    assert event.schema_version == 1
    assert event.payload["applied"] == 40


def test_operational_event_rejects_unknown_kind() -> None:
    try:
        OperationalEvent(event_type="unknown", event_kind="recipe", source_id="mes")
    except ValueError as exc:
        assert "event_kind" in str(exc)
    else:
        raise AssertionError("invalid operational event kind was accepted")

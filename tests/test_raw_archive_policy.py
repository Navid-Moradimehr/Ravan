from __future__ import annotations

from services.processor.raw_archive_policy import sanitize_raw_event


def test_raw_archive_redacts_configured_fields():
    event, reason = sanitize_raw_event({"event_id": "e1", "secret": "value"}, redact_fields=("secret",))
    assert reason is None
    assert event is not None
    assert event["secret"] == "[REDACTED]"
    assert "value" not in event["payload_json"]


def test_raw_archive_rejects_oversized_payload():
    event, reason = sanitize_raw_event({"payload": "x" * 100}, max_bytes=20)
    assert event is None
    assert reason and "exceeds max bytes" in reason

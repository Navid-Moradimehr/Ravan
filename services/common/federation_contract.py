"""Versioned contract for events forwarded between Ravan deployments.

The contract is deliberately transport-neutral. Kafka, HTTP, and future
connectors can use the same envelope without changing the canonical event.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

FEDERATION_ENVELOPE_VERSION = 1
FEDERATION_ENVELOPE_TYPE = "ravan.federated_event"
REQUIRED_ORIGIN_FIELDS = (
    "site_id",
    "deployment_id",
    "source_id",
    "event_id",
    "topic",
    "schema_version",
    "processing_version",
    "forwarded_at",
)


class FederationContractError(ValueError):
    """Raised when a forwarded event cannot be trusted or replayed safely."""


def _text(value: Any) -> str:
    return str(value).strip() if value is not None else ""


def wrap_event(
    event: dict[str, Any],
    *,
    site_id: str,
    deployment_id: str,
    topic: str,
    processing_version: str = "",
    forwarded_at: str | None = None,
) -> dict[str, Any]:
    """Wrap a canonical event while preserving its payload unchanged."""
    event_id = _text(event.get("event_id"))
    source_id = _text(event.get("source_id"))
    schema_version = event.get("schema_version", 1)
    if not event_id or not source_id:
        raise FederationContractError("event_id and source_id are required before forwarding")
    return {
        "envelope_type": FEDERATION_ENVELOPE_TYPE,
        "envelope_version": FEDERATION_ENVELOPE_VERSION,
        "origin": {
            "site_id": _text(site_id),
            "deployment_id": _text(deployment_id),
            "source_id": source_id,
            "event_id": event_id,
            "topic": _text(topic),
            "schema_version": int(schema_version),
            "processing_version": _text(processing_version) or "unknown",
            "forwarded_at": forwarded_at or datetime.now(timezone.utc).isoformat(),
        },
        "payload": event,
    }


def validate_envelope(value: Any) -> list[str]:
    """Return actionable validation errors without mutating the payload."""
    if not isinstance(value, dict):
        return ["envelope must be an object"]
    if value.get("envelope_type") != FEDERATION_ENVELOPE_TYPE:
        return ["unsupported envelope_type"]
    if value.get("envelope_version") != FEDERATION_ENVELOPE_VERSION:
        return ["unsupported envelope_version"]
    origin = value.get("origin")
    if not isinstance(origin, dict):
        return ["origin must be an object"]
    errors = [f"origin.{field} is missing" for field in REQUIRED_ORIGIN_FIELDS if not _text(origin.get(field))]
    if not isinstance(origin.get("schema_version"), int):
        errors.append("origin.schema_version must be an integer")
    payload = value.get("payload")
    if not isinstance(payload, dict):
        errors.append("payload must be an object")
    elif _text(payload.get("event_id")) != _text(origin.get("event_id")):
        errors.append("origin.event_id does not match payload.event_id")
    elif _text(payload.get("source_id")) != _text(origin.get("source_id")):
        errors.append("origin.source_id does not match payload.source_id")
    return errors


def unwrap_event(value: dict[str, Any], *, allow_legacy: bool = True) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return canonical payload and forwarding metadata.

    Legacy messages are accepted for compatibility but explicitly marked so
    operators can migrate producers without silently losing provenance.
    """
    if value.get("envelope_type") is None:
        if not allow_legacy:
            raise FederationContractError("legacy unwrapped event is not allowed")
        return value, {"legacy": True}
    errors = validate_envelope(value)
    if errors:
        raise FederationContractError("; ".join(errors))
    return value["payload"], {"legacy": False, **value["origin"]}


def deduplication_key(value: dict[str, Any], *, topic: str | None = None) -> str:
    """Build a stable origin key for at-least-once federation delivery."""
    if value.get("envelope_type"):
        origin = value.get("origin") or {}
        parts = (origin.get("site_id"), origin.get("source_id"), origin.get("topic"), origin.get("event_id"))
    else:
        parts = (value.get("site_id") or value.get("site"), value.get("source_id"), topic or "", value.get("event_id"))
    if not all(_text(part) for part in parts):
        raise FederationContractError("site_id, source_id, topic, and event_id are required for deduplication")
    return "|".join(_text(part) for part in parts)

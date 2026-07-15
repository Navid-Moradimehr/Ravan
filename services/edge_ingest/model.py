from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator

from services.common.wire_format import deserialize_payload as deserialize_wire_payload
from services.common.wire_format import serialize_payload as serialize_wire_payload


Protocol = Literal[
    "opcua",
    "mqtt",
    "modbus",
    "modbus_rtu",
    "sparkplug_b",
    "dataset",
    "mock",
    "api",
]
Quality = Literal["good", "uncertain", "bad"]


class IndustrialEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_protocol: Protocol
    source_id: str
    asset_id: str
    tag: str
    value: float | int | bool | str
    quality: Quality = "good"
    unit: str | None = None
    site: str = "demo-site"
    line: str = "line-01"
    ts_source: str
    ts_ingest: str = Field(default_factory=lambda: utc_now())
    schema_version: int = 1
    source_connection_id: str = ""
    source_config_version: int = 0
    mapping_version: str = ""
    lineage_id: str = ""
    sequence_number: int | None = Field(default=None, ge=0)
    clock_id: str = ""
    clock_sync_status: str = ""
    timestamp_uncertainty_ms: float | None = Field(default=None, ge=0)
    calibration_version: str = ""
    topology_version: str = ""
    context_id: str = ""

    @field_validator("tag", "asset_id", "source_id")
    @classmethod
    def require_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value


class DeadLetterEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_protocol: str
    source_id: str
    error: str
    payload: dict[str, Any] | str
    ts_ingest: str = Field(default_factory=lambda: utc_now())
    schema_version: int = 1
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_event(payload: dict[str, Any]) -> tuple[IndustrialEvent | None, DeadLetterEvent | None]:
    try:
        return IndustrialEvent.model_validate(payload), None
    except ValidationError as exc:
        return None, DeadLetterEvent(
            source_protocol=str(payload.get("source_protocol", "unknown")),
            source_id=str(payload.get("source_id", "unknown")),
            error=exc.errors(include_url=False).__repr__(),
            payload=payload,
        )


def to_wire_bytes(payload: BaseModel | dict[str, Any], wire_format: str | None = None) -> bytes:
    if wire_format is None:
        wire_format = os.getenv("DATASTREAM_WIRE_FORMAT", "json")
    return serialize_wire_payload(payload, wire_format=wire_format)


def to_json_bytes(payload: BaseModel | dict[str, Any]) -> bytes:
    return serialize_wire_payload(payload, wire_format="json")


def from_wire_bytes(data: bytes, wire_format: str | None = None) -> Any:
    return deserialize_wire_payload(data, wire_format=wire_format)

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError, field_validator


Protocol = Literal["opcua", "mqtt", "modbus"]
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


def to_json_bytes(payload: BaseModel | dict[str, Any]) -> bytes:
    if isinstance(payload, BaseModel):
        return payload.model_dump_json(separators=(",", ":")).encode("utf-8")
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")

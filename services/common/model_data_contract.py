"""Contracts for preserving model-training evidence without training models.

The platform keeps high-volume scalar telemetry and large media payloads on
separate paths. Kafka carries the metadata and immutable object references;
operators keep the referenced bytes in their configured object store.
"""

from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


Modality = Literal[
    "image",
    "video",
    "audio",
    "waveform",
    "tensor",
    "document",
    "lidar",
    "thermal",
]


class ObservationArtifactReference(BaseModel):
    """An immutable reference to a non-scalar observation artifact."""

    artifact_id: str = Field(min_length=1, max_length=256)
    event_id: str = ""
    site_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=256)
    entity_id: str = ""
    modality: Modality
    uri: str = Field(min_length=1, max_length=2048)
    sha256: str = ""
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str = ""
    encoding: str = ""
    shape: tuple[int, ...] = ()
    sample_rate_hz: float | None = Field(default=None, gt=0)
    frame_rate_hz: float | None = Field(default=None, gt=0)
    started_at: str = ""
    ended_at: str = ""
    clock_id: str = ""
    calibration_version: str = ""
    topology_version: str = ""
    schema_version: int = Field(default=1, ge=1)
    lineage_id: str = ""

    @field_validator("uri")
    @classmethod
    def validate_uri_scheme(cls, value: str) -> str:
        if not value.startswith(("s3://", "file://")):
            raise ValueError("artifact uri must use an allowed s3:// or file:// scheme")
        return value

    @field_validator("sha256")
    @classmethod
    def validate_checksum(cls, value: str) -> str:
        if value and (len(value) != 64 or any(char not in "0123456789abcdefABCDEF" for char in value)):
            raise ValueError("sha256 must be a 64-character hexadecimal digest")
        return value.lower()


class ActionPayload(BaseModel):
    action_id: str = Field(min_length=1, max_length=256)
    command: str = Field(min_length=1, max_length=256)
    requested_value: Any = None
    applied_value: Any = None
    unit: str = ""
    status: Literal["requested", "accepted", "applied", "rejected", "overridden", "unknown"] = "unknown"
    effective_at: str = ""
    duration_ms: int | None = Field(default=None, ge=0)
    control_mode: str = ""


class OutcomePayload(BaseModel):
    outcome_id: str = Field(min_length=1, max_length=256)
    action_id: str = ""
    metric: str = Field(min_length=1, max_length=256)
    value: float | int | bool | str
    unit: str = ""
    success: bool | None = None
    observed_at: str = ""
    reward: float | None = None


class EpisodeBoundaryPayload(BaseModel):
    episode_id: str = Field(min_length=1, max_length=256)
    boundary_type: Literal["start", "end", "truncate", "reset"]
    reason: str = ""
    step: int | None = Field(default=None, ge=0)


def checksum_bytes(payload: bytes) -> str:
    """Return the stable digest used by artifact verification."""

    return hashlib.sha256(payload).hexdigest()


def validate_standard_operational_payload(event_kind: str, payload: dict[str, Any], schema_ref: str = "") -> dict[str, Any]:
    """Validate declared standard payloads while preserving custom extensions."""

    if not schema_ref:
        return payload
    validators = {
        "industrial.action.v1": ActionPayload,
        "industrial.outcome.v1": OutcomePayload,
        "industrial.boundary.v1": EpisodeBoundaryPayload,
    }
    model = validators.get(schema_ref)
    if model is None:
        raise ValueError(f"unsupported operational payload schema: {schema_ref}")
    expected_kind = {
        "industrial.action.v1": "action",
        "industrial.outcome.v1": "outcome",
        "industrial.boundary.v1": "boundary",
    }[schema_ref]
    if event_kind != expected_kind:
        raise ValueError(f"{schema_ref} requires event_kind={expected_kind}")
    return model.model_validate(payload).model_dump(mode="json")

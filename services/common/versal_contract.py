"""Contracts for AMD Versal/FPGA gateway integrations.

Ravan consumes normalized industrial telemetry and immutable references to
high-volume simulator or hardware artifacts.  The contract deliberately keeps
register/DMA details at the gateway boundary.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from services.common.model_data_contract import ObservationArtifactReference


class VersalDeviceMetadata(BaseModel):
    vendor: str = "amd"
    family: str = "versal"
    board: str = Field(min_length=1, max_length=128)
    device_id: str = Field(min_length=1, max_length=256)
    firmware_version: str = ""
    bitstream_id: str = ""
    vitis_version: str = ""
    xrt_version: str = ""
    register_map_version: str = ""
    clock_id: str = ""
    clock_sync_status: str = ""


class VersalMetric(BaseModel):
    asset_id: str = Field(min_length=1, max_length=256)
    tag: str = Field(min_length=1, max_length=256)
    value: float | int | bool | str
    unit: str = ""
    quality: Literal["good", "uncertain", "bad"] = "good"
    ts_source: str
    sequence_number: int | None = Field(default=None, ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("ts_source")
    @classmethod
    def timezone_aware_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("ts_source must include a timezone")
        return value


class VersalRunManifest(BaseModel):
    """A simulator or hardware run summary, never a raw waveform container."""

    schema_version: int = Field(default=1, ge=1)
    run_id: str = Field(min_length=1, max_length=256)
    source_id: str = Field(min_length=1, max_length=256)
    site_id: str = Field(min_length=1, max_length=256)
    device: VersalDeviceMetadata
    simulator: Literal["gateway", "verilator", "vitis_sw_emu", "vitis_hw_emu", "hardware"]
    status: Literal["passed", "failed", "cancelled", "unknown"] = "unknown"
    started_at: str = ""
    ended_at: str = ""
    metrics: list[VersalMetric] = Field(default_factory=list)
    artifacts: list[ObservationArtifactReference] = Field(default_factory=list)
    lineage_id: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


def device_profile_config(*, board: str, device_id: str, gateway: str = "sparkplug_b") -> dict[str, Any]:
    """Return a safe source config preset for a Versal-side gateway."""

    if gateway not in {"sparkplug_b", "opcua"}:
        raise ValueError("gateway must be sparkplug_b or opcua")
    return {
        "device_profile": "amd_versal_v1",
        "gateway_protocol": gateway,
        "versal": {"board": board, "device_id": device_id, "telemetry_mode": "scalar_plus_artifacts"},
    }

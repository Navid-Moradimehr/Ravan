"""Deterministic, hardware-free Versal gateway simulator.

The simulator produces the same normalized metric and artifact metadata used by
Sparkplug/OPC UA gateway adapters.  A deployment wrapper can publish the
returned dictionaries to MQTT, while unit tests remain broker-free.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Iterator

from services.common.model_data_contract import ObservationArtifactReference
from services.common.versal_contract import VersalDeviceMetadata, VersalMetric, VersalRunManifest


def _timestamp(start: datetime, offset: int) -> str:
    return (start + timedelta(seconds=offset)).isoformat()


def iter_metrics(*, source_id: str, site_id: str, start: datetime, count: int = 10) -> Iterator[VersalMetric]:
    """Yield stable scalar telemetry for golden tests and local smoke runs."""

    for index in range(count):
        yield VersalMetric(
            asset_id=f"{source_id}:kernel-0",
            tag="kernel_latency_ms",
            value=2.5 + (index % 4) * 0.25,
            unit="ms",
            ts_source=_timestamp(start, index),
            sequence_number=index,
            metadata={"device_profile": "amd_versal_v1", "engine": "aie"},
        )
        yield VersalMetric(
            asset_id=f"{source_id}:capture-0",
            tag="vibration_rms",
            value=1.2 + (index % 3) * 0.1,
            unit="mm/s",
            ts_source=_timestamp(start, index),
            sequence_number=index,
            metadata={"device_profile": "amd_versal_v1", "derived": "fft_rms"},
        )


def build_manifest(*, source_id: str, site_id: str, run_id: str = "versal-sim-1", simulator: str = "gateway") -> VersalRunManifest:
    start = datetime.now(timezone.utc).replace(microsecond=0)
    payload = f"{run_id}:{source_id}".encode("utf-8")
    artifact = ObservationArtifactReference(
        artifact_id=f"{run_id}:waveform",
        event_id=f"{run_id}:event-0",
        site_id=site_id,
        source_id=source_id,
        entity_id=f"{source_id}:capture-0",
        modality="waveform",
        uri=f"file:///ravan-sim/{run_id}.vcd",
        sha256=hashlib.sha256(payload).hexdigest(),
        size_bytes=len(payload),
        content_type="application/vnd.eda.vcd",
        encoding="vcd",
        shape=(1024,),
        sample_rate_hz=10_000,
        started_at=start.isoformat(),
        ended_at=_timestamp(start, 9),
        clock_id=f"{source_id}:clock",
        schema_version=1,
        lineage_id=run_id,
    )
    return VersalRunManifest(
        run_id=run_id,
        source_id=source_id,
        site_id=site_id,
        device=VersalDeviceMetadata(board="simulated-vck190", device_id=f"sim:{source_id}", bitstream_id="golden-bitstream-v1", register_map_version="versal-gateway-v1", clock_id=f"{source_id}:clock", clock_sync_status="simulated"),
        simulator=simulator, status="passed", started_at=start.isoformat(), ended_at=_timestamp(start, 9),
        metrics=list(iter_metrics(source_id=source_id, site_id=site_id, start=start, count=10)),
        artifacts=[artifact], lineage_id=run_id,
    )

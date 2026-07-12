"""Contracts for protocol-faithful, end-to-end industrial soak tests."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_PROTOCOLS = {"opcua", "mqtt", "modbus", "sparkplug_b", "replay"}
SUPPORTED_PHASES = {"warmup", "sustained", "burst", "reconnect", "restart", "recovery", "drain"}


@dataclass(frozen=True)
class SoakSource:
    source_id: str
    protocol: str
    site_id: str
    asset_prefix: str
    device_count: int
    rate_per_second: float

    @property
    def events_per_second(self) -> float:
        return self.device_count * self.rate_per_second


@dataclass(frozen=True)
class SoakPhase:
    name: str
    duration_seconds: int
    rate_multiplier: float = 1.0
    fault: str = ""
    restart_service: str = ""


@dataclass(frozen=True)
class SoakAcceptance:
    max_dlq_rate: float = 0.0
    max_unaccounted_events: int = 0
    max_memory_growth_mb: float = 512.0
    drain_timeout_seconds: int = 180


@dataclass(frozen=True)
class IndustrialSoakScenario:
    schema_version: int
    scenario_id: str
    duration_seconds: int
    sources: tuple[SoakSource, ...]
    phases: tuple[SoakPhase, ...]
    processor_mode: str = "python-fallback"
    ai_enabled: bool = False
    acceptance: SoakAcceptance = SoakAcceptance()

    @property
    def configured_events_per_second(self) -> float:
        return sum(source.events_per_second for source in self.sources)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema_version != 1:
            errors.append(f"unsupported schema_version: {self.schema_version}")
        if not self.scenario_id.strip():
            errors.append("scenario_id is required")
        if self.duration_seconds <= 0:
            errors.append("duration_seconds must be positive")
        source_ids = [source.source_id for source in self.sources]
        if not source_ids:
            errors.append("at least one source is required")
        if len(set(source_ids)) != len(source_ids):
            errors.append("source_id values must be unique")
        for source in self.sources:
            if source.protocol not in SUPPORTED_PROTOCOLS:
                errors.append(f"source {source.source_id}: unsupported protocol {source.protocol}")
            if not source.site_id.strip():
                errors.append(f"source {source.source_id}: site_id is required")
            if source.device_count <= 0:
                errors.append(f"source {source.source_id}: device_count must be positive")
            if source.rate_per_second <= 0:
                errors.append(f"source {source.source_id}: rate_per_second must be positive")
        phase_names = [phase.name for phase in self.phases]
        if not self.phases:
            errors.append("at least one phase is required")
        if len(set(phase_names)) != len(phase_names):
            errors.append("phase names must be unique")
        phase_seconds = 0
        for phase in self.phases:
            if phase.name not in SUPPORTED_PHASES:
                errors.append(f"unsupported phase: {phase.name}")
            if phase.duration_seconds <= 0:
                errors.append(f"phase {phase.name}: duration_seconds must be positive")
            if phase.rate_multiplier < 0:
                errors.append(f"phase {phase.name}: rate_multiplier cannot be negative")
            phase_seconds += phase.duration_seconds
        if phase_seconds != self.duration_seconds:
            errors.append(
                f"phase durations must equal duration_seconds ({phase_seconds} != {self.duration_seconds})"
            )
        if self.acceptance.max_dlq_rate < 0 or self.acceptance.max_unaccounted_events < 0:
            errors.append("acceptance limits cannot be negative")
        return errors


def _source(raw: dict[str, Any]) -> SoakSource:
    return SoakSource(
        source_id=str(raw.get("source_id", "")).strip(),
        protocol=str(raw.get("protocol", "")).strip().lower(),
        site_id=str(raw.get("site_id", "")).strip(),
        asset_prefix=str(raw.get("asset_prefix", "Asset")).strip(),
        device_count=int(raw.get("device_count", 1)),
        rate_per_second=float(raw.get("rate_per_second", 1.0)),
    )


def _phase(raw: dict[str, Any]) -> SoakPhase:
    return SoakPhase(
        name=str(raw.get("name", "")).strip().lower(),
        duration_seconds=int(raw.get("duration_seconds", 0)),
        rate_multiplier=float(raw.get("rate_multiplier", 1.0)),
        fault=str(raw.get("fault", "")).strip(),
        restart_service=str(raw.get("restart_service", "")).strip(),
    )


def load_scenario(path: Path | str) -> IndustrialSoakScenario:
    payload = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    acceptance = payload.get("acceptance") or {}
    scenario = IndustrialSoakScenario(
        schema_version=int(payload.get("schema_version", 1)),
        scenario_id=str(payload.get("scenario_id", "")).strip(),
        duration_seconds=int(payload.get("duration_seconds", 0)),
        sources=tuple(_source(item) for item in payload.get("sources", [])),
        phases=tuple(_phase(item) for item in payload.get("phases", [])),
        processor_mode=str(payload.get("processor_mode", "python-fallback")).strip(),
        ai_enabled=bool(payload.get("ai_enabled", False)),
        acceptance=SoakAcceptance(
            max_dlq_rate=float(acceptance.get("max_dlq_rate", 0.0)),
            max_unaccounted_events=int(acceptance.get("max_unaccounted_events", 0)),
            max_memory_growth_mb=float(acceptance.get("max_memory_growth_mb", 512.0)),
            drain_timeout_seconds=int(acceptance.get("drain_timeout_seconds", 180)),
        ),
    )
    errors = scenario.validate()
    if errors:
        raise ValueError("invalid industrial soak scenario: " + "; ".join(errors))
    return scenario

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


@dataclass(frozen=True)
class ProtocolProfile:
    protocol: str
    transport: str
    typical_devices: tuple[str, ...]
    strengths: tuple[str, ...]
    edge_cases: tuple[str, ...]
    notes: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROTOCOL_PROFILES: dict[str, ProtocolProfile] = {
    "opcua": ProtocolProfile(
        protocol="opcua",
        transport="TCP",
        typical_devices=("Siemens", "Beckhoff", "Schneider", "B&R", "Phoenix Contact", "industrial sensors with UA servers"),
        strengths=(
            "rich information models",
            "built-in security and discovery",
            "good fit for mixed vendors and multi-site integration",
        ),
        edge_cases=(
            "namespace and node-id drift across vendors",
            "certificate trust management",
            "subscription rate and sampling limits on small PLCs",
        ),
        notes=(
            "best default for heterogeneous PLC fleets",
            "works well when vendor-specific tags must be normalized into a common model",
        ),
    ),
    "modbus": ProtocolProfile(
        protocol="modbus",
        transport="TCP",
        typical_devices=("Modicon/Schneider", "generic PLCs", "gateways", "meters", "simple sensors"),
        strengths=(
            "simple register model",
            "widely supported by PLCs and meters",
            "easy to simulate and bridge",
        ),
        edge_cases=(
            "endianness and word-order mismatches",
            "ambiguous register maps",
            "polling latency and register churn",
        ),
        notes=(
            "good compatibility baseline for brownfield plants",
            "best used behind a gateway when multiple devices share one bus",
        ),
    ),
    "modbus_rtu": ProtocolProfile(
        protocol="modbus_rtu",
        transport="serial",
        typical_devices=("legacy PLCs", "RTUs", "serial meters", "remote I/O", "field instruments"),
        strengths=(
            "cheap legacy coverage",
            "works over RS-485 plant wiring",
            "useful for brownfield retrofits",
        ),
        edge_cases=(
            "baud and framing mismatches",
            "bus contention on shared serial trunks",
            "long cable noise and timing sensitivity",
        ),
        notes=(
            "important for older industrial units",
            "usually benefits from a protocol gateway for scalable ingestion",
        ),
    ),
    "mqtt": ProtocolProfile(
        protocol="mqtt",
        transport="TCP",
        typical_devices=("edge gateways", "IIoT sensors", "vendor bridges", "SPC/utility devices"),
        strengths=(
            "lightweight publish/subscribe",
            "good for edge-to-platform fan-out",
            "easy to bridge across sites",
        ),
        edge_cases=(
            "topic design drift",
            "QoS semantics across brokers",
            "payload shape variation between vendors",
        ),
        notes=(
            "works well when PLCs publish through an edge gateway",
            "Sparkplug B is preferred when a stricter industrial MQTT contract is needed",
        ),
    ),
    "sparkplug_b": ProtocolProfile(
        protocol="sparkplug_b",
        transport="MQTT",
        typical_devices=("Ignition ecosystems", "sparkplug-enabled gateways", "IIoT edge nodes"),
        strengths=(
            "structured MQTT telemetry",
            "birth/death model for device lifecycle",
            "good for fleet-wide consistency",
        ),
        edge_cases=(
            "protobuf/schema compatibility",
            "birth/death state handling",
            "payload version drift",
        ),
        notes=(
            "better than plain MQTT when device identity and lifecycle matter",
            "good fit for large multi-site rollouts with edge gateways",
        ),
    ),
    "api": ProtocolProfile(
        protocol="api",
        transport="HTTP",
        typical_devices=("external systems", "MES/ERP bridges", "manual integrations"),
        strengths=("integration flexibility", "simple operator-driven ingestion"),
        edge_cases=("caller responsibility for payload correctness", "rate limiting and idempotency"),
        notes=("not a device protocol, but a useful ingest contract for integrations"),
    ),
    "dataset": ProtocolProfile(
        protocol="dataset",
        transport="file/batch",
        typical_devices=("replay packs", "benchmark inputs", "historical exports"),
        strengths=("repeatable testing", "easy benchmark generation"),
        edge_cases=("schema drift", "timestamp normalization"),
        notes=("used for offline simulation and benchmarking"),
    ),
    "mock": ProtocolProfile(
        protocol="mock",
        transport="local",
        typical_devices=("simulators", "test rigs"),
        strengths=("fast local smoke tests", "deterministic benchmark input"),
        edge_cases=("not representative of field wiring",),
        notes=("useful for CI and local validation"),
    ),
}


def supported_protocols() -> tuple[str, ...]:
    return tuple(PROTOCOL_PROFILES)


def protocol_profile(protocol: str) -> ProtocolProfile | None:
    return PROTOCOL_PROFILES.get(str(protocol).strip().lower())


def tag_to_legacy_field(tag: str) -> str | None:
    lowered = str(tag).lower()
    if "temp" in lowered:
        return "temperature_c"
    if "vibration" in lowered:
        return "vibration_mm_s"
    if "pressure" in lowered:
        return "pressure_bar"
    return None


def unit_for_tag(tag: str) -> str:
    lowered = str(tag).lower()
    if "temp" in lowered:
        return "c"
    if "vibration" in lowered:
        return "mm/s"
    if "pressure" in lowered:
        return "bar"
    return ""

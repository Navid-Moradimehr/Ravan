from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from services.common.device_compat import tag_to_legacy_field


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _build_record_from_mapping(event: dict[str, Any]) -> "RuntimeEventRecord":
    get = event.get
    tag = str(get("tag", ""))
    value = _to_float(get("value", 0))
    record = RuntimeEventRecord(
        event_id=str(get("event_id", "")),
        source_protocol=str(get("source_protocol", "unknown")),
        source_id=str(get("source_id", get("asset_id", "unknown-source"))),
        asset_id=str(get("asset_id", "unknown-asset")),
        tag=tag,
        value=value,
        quality=str(get("quality", "good")),
        unit=str(get("unit", "") or ""),
        site_id=str(get("site", get("site_id", "demo-site"))),
        line=str(get("line", get("line_id", "line-01"))),
        schema_version=_to_int(get("schema_version", 1), 1),
        timestamp=str(get("ts_source") or get("ts_ingest") or ""),
        device_id=str(get("asset_id", get("device_id", "unknown-asset"))),
        project_id=str(get("project_id", get("site", get("site_id", ""))) or ""),
        source_connection_id=str(get("source_connection_id", "")),
        source_config_version=_to_int(get("source_config_version", 0), 0),
        mapping_version=str(get("mapping_version", "")),
        lineage_id=str(get("lineage_id", get("event_id", ""))),
        fault_type=str(get("fault_type", "normal")),
        scenario_id=str(get("scenario_id", "sc-000")),
        ground_truth_severity=str(get("ground_truth_severity", "normal")),
    )
    legacy_field = tag_to_legacy_field(tag)
    if legacy_field == "temperature_c":
        record.temperature_c = value
    elif legacy_field == "vibration_mm_s":
        record.vibration_mm_s = value
    elif legacy_field == "pressure_bar":
        record.pressure_bar = value
    return record


@dataclass(slots=True)
class RuntimeEventRecord:
    event_id: str
    source_protocol: str
    source_id: str
    asset_id: str
    tag: str
    value: float
    quality: str
    unit: str
    site_id: str
    line: str
    schema_version: int
    timestamp: str
    device_id: str
    project_id: str = ""
    source_connection_id: str = ""
    source_config_version: int = 0
    mapping_version: str = ""
    lineage_id: str = ""
    temperature_c: float = 0.0
    vibration_mm_s: float = 0.0
    pressure_bar: float = 0.0
    fault_type: str = "normal"
    scenario_id: str = "sc-000"
    ground_truth_severity: str = "normal"
    processed_at: str = ""
    window_size: int = 0
    temperature_avg_c: float = 0.0
    vibration_avg_mm_s: float = 0.0
    anomaly_score: float = 0.0
    severity: str = "normal"
    threshold_severity: str = "normal"
    threshold_status: str = "unconfigured"
    threshold_source: str = "unconfigured"
    threshold_policy_version: int = 0
    threshold_breached: bool = False
    triggered_rules: tuple[str, ...] = field(default_factory=tuple)
    baseline: dict[str, Any] | None = None
    evaluation: dict[str, Any] | None = None
    _partition_key_cache: bytes = field(default=b"", init=False, repr=False)

    def __post_init__(self) -> None:
        project_id = self.project_id or self.site_id
        self._partition_key_cache = "|".join(
            [
                project_id,
                self.site_id,
                self.line,
                self.source_protocol,
                self.source_id,
                self.asset_id,
                self.tag,
            ]
        ).encode("utf-8")

    @classmethod
    def from_raw_mapping(cls, event: dict[str, Any]) -> "RuntimeEventRecord":
        return _build_record_from_mapping(event)

    @classmethod
    def from_industrial_event(cls, event: Any) -> "RuntimeEventRecord":
        if isinstance(event, dict):
            return _build_record_from_mapping(event)
        data = getattr(event, "__dict__", None)
        if isinstance(data, dict) and data:
            return _build_record_from_mapping(data)
        if hasattr(event, "model_dump"):
            return _build_record_from_mapping(event.model_dump(mode="python"))
        return _build_record_from_mapping(dict(event))

    def partition_key(self) -> bytes:
        return self._partition_key_cache

    def mark_processed(
        self,
        *,
        processed_at: str | None = None,
        window_size: int = 0,
        temperature_avg_c: float = 0.0,
        vibration_avg_mm_s: float = 0.0,
        anomaly_score: float = 0.0,
        severity: str = "normal",
        threshold_severity: str = "normal",
        threshold_status: str = "unconfigured",
        threshold_source: str = "unconfigured",
        threshold_policy_version: int = 0,
        threshold_breached: bool = False,
        triggered_rules: tuple[str, ...] | None = None,
        baseline: dict[str, Any] | None = None,
        evaluation: dict[str, Any] | None = None,
    ) -> None:
        self.processed_at = processed_at or datetime.now(timezone.utc).isoformat()
        self.window_size = window_size
        self.temperature_avg_c = temperature_avg_c
        self.vibration_avg_mm_s = vibration_avg_mm_s
        self.anomaly_score = anomaly_score
        self.severity = severity
        self.threshold_severity = threshold_severity
        self.threshold_status = threshold_status
        self.threshold_source = threshold_source
        self.threshold_policy_version = threshold_policy_version
        self.threshold_breached = threshold_breached
        if triggered_rules is not None:
            self.triggered_rules = triggered_rules
        self.baseline = baseline
        self.evaluation = evaluation

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "event_id": self.event_id,
            "source_protocol": self.source_protocol,
            "source_id": self.source_id,
            "asset_id": self.asset_id,
            "tag": self.tag,
            "value": self.value,
            "quality": self.quality,
            "unit": self.unit,
            "site_id": self.site_id,
            "line": self.line,
            "schema_version": self.schema_version,
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "project_id": self.project_id,
            "source_connection_id": self.source_connection_id,
            "source_config_version": self.source_config_version,
            "mapping_version": self.mapping_version,
            "lineage_id": self.lineage_id,
            "temperature_c": self.temperature_c,
            "vibration_mm_s": self.vibration_mm_s,
            "pressure_bar": self.pressure_bar,
            "fault_type": self.fault_type,
            "scenario_id": self.scenario_id,
            "ground_truth_severity": self.ground_truth_severity,
            "processed_at": self.processed_at,
            "window_size": self.window_size,
            "temperature_avg_c": self.temperature_avg_c,
            "vibration_avg_mm_s": self.vibration_avg_mm_s,
            "anomaly_score": self.anomaly_score,
            "severity": self.severity,
            "threshold_severity": self.threshold_severity,
            "threshold_status": self.threshold_status,
            "threshold_source": self.threshold_source,
            "threshold_policy_version": self.threshold_policy_version,
            "threshold_breached": self.threshold_breached,
            "triggered_rules": list(self.triggered_rules),
        }
        if self.baseline is not None:
            payload["baseline"] = self.baseline
        if self.evaluation is not None:
            payload["evaluation"] = self.evaluation
        return payload


@dataclass(slots=True)
class RollingWindowState:
    maxlen: int
    records: deque[RuntimeEventRecord] = field(default_factory=deque)
    temperature_sum: float = 0.0
    vibration_sum: float = 0.0

    def append(self, record: RuntimeEventRecord) -> tuple[float, float, int]:
        if self.maxlen <= 0:
            self.maxlen = 1
        if len(self.records) >= self.maxlen:
            evicted = self.records.popleft()
            self.temperature_sum -= evicted.temperature_c
            self.vibration_sum -= evicted.vibration_mm_s

        self.records.append(record)
        self.temperature_sum += record.temperature_c
        self.vibration_sum += record.vibration_mm_s
        size = len(self.records)
        if size <= 0:
            return 0.0, 0.0, 0
        return self.temperature_sum / size, self.vibration_sum / size, size

from __future__ import annotations

from dataclasses import dataclass

from services.common.runtime_event import RuntimeEventRecord
from services.processor.scoring import score_event, severity_for


@dataclass(slots=True, frozen=True)
class RuntimeEnrichmentResult:
    temperature_avg_c: float
    vibration_avg_mm_s: float
    window_size: int
    anomaly_score: float
    severity: str


def build_runtime_event_payload(
    event: RuntimeEventRecord,
    *,
    temperature_avg_c: float,
    vibration_avg_mm_s: float,
    window_size: int,
) -> dict[str, object]:
    """Apply the shared runtime enrichment contract and return the serialized payload.

    The processor hot path and the Flink job both need to attach the same scoring
    and severity metadata. Keeping the mutation in one helper prevents drift
    between the Python fallback runtime and the distributed job.
    """

    result = enrich_runtime_event(
        event,
        temperature_avg_c=temperature_avg_c,
        vibration_avg_mm_s=vibration_avg_mm_s,
        window_size=window_size,
    )
    payload = event.to_dict()
    payload["temperature_avg_c"] = result.temperature_avg_c
    payload["vibration_avg_mm_s"] = result.vibration_avg_mm_s
    payload["window_size"] = result.window_size
    payload["anomaly_score"] = result.anomaly_score
    payload["severity"] = result.severity
    return payload


def enrich_runtime_event(
    event: RuntimeEventRecord,
    *,
    temperature_avg_c: float,
    vibration_avg_mm_s: float,
    window_size: int,
) -> RuntimeEnrichmentResult:
    anomaly_score = score_event(event, temperature_avg_c, vibration_avg_mm_s)
    severity = severity_for(anomaly_score)
    event.mark_processed(
        window_size=window_size,
        temperature_avg_c=round(temperature_avg_c, 2),
        vibration_avg_mm_s=round(vibration_avg_mm_s, 2),
        anomaly_score=anomaly_score,
        severity=severity,
    )
    return RuntimeEnrichmentResult(
        temperature_avg_c=round(temperature_avg_c, 2),
        vibration_avg_mm_s=round(vibration_avg_mm_s, 2),
        window_size=window_size,
        anomaly_score=anomaly_score,
        severity=severity,
    )

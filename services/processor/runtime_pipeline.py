from __future__ import annotations

from dataclasses import dataclass

from services.common.runtime_event import RuntimeEventRecord
from services.processor.scoring import score_event, severity_for
from services.common.threshold_policy import evaluate_threshold_runtime, resolve_threshold_policy


@dataclass(slots=True, frozen=True)
class RuntimeEnrichmentResult:
    temperature_avg_c: float
    vibration_avg_mm_s: float
    window_size: int
    anomaly_score: float
    severity: str
    threshold_severity: str
    threshold_status: str
    threshold_source: str
    threshold_policy_version: int
    threshold_breached: bool


def build_runtime_event_payload(
    event: RuntimeEventRecord,
    *,
    temperature_avg_c: float,
    vibration_avg_mm_s: float,
    window_size: int,
    threshold_policy: dict[str, object] | None = None,
    threshold_result: dict[str, object] | None = None,
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
        threshold_policy=threshold_policy,
        threshold_result=threshold_result,
    )
    payload = event.to_dict()
    payload["temperature_avg_c"] = result.temperature_avg_c
    payload["vibration_avg_mm_s"] = result.vibration_avg_mm_s
    payload["window_size"] = result.window_size
    payload["anomaly_score"] = result.anomaly_score
    payload["severity"] = result.severity
    payload["threshold_severity"] = result.threshold_severity
    payload["threshold_status"] = result.threshold_status
    payload["threshold_source"] = result.threshold_source
    payload["threshold_policy_version"] = result.threshold_policy_version
    payload["threshold_breached"] = result.threshold_breached
    return payload


def enrich_runtime_event(
    event: RuntimeEventRecord,
    *,
    temperature_avg_c: float,
    vibration_avg_mm_s: float,
    window_size: int,
    threshold_policy: dict[str, object] | None = None,
    threshold_result: dict[str, object] | None = None,
) -> RuntimeEnrichmentResult:
    anomaly_score = score_event(event, temperature_avg_c, vibration_avg_mm_s)
    anomaly_severity = severity_for(anomaly_score)
    policy = threshold_policy or resolve_threshold_policy(event.site_id, event.asset_id, event.tag)
    threshold = threshold_result or evaluate_threshold_runtime(
        f"{event.site_id}:{event.asset_id}:{event.tag}", event.value, policy, quality=event.quality
    )
    severity_rank = {"normal": 0, "warning": 1, "critical": 2}
    severity = max((anomaly_severity, threshold["severity"]), key=lambda item: severity_rank[item])
    threshold_severity = str(threshold["severity"])
    evaluation = {
        "anomaly_severity": anomaly_severity,
        "threshold_severity": threshold_severity,
        "threshold_status": threshold["status"],
        "threshold_source": policy.get("source", "unconfigured"),
        "threshold_policy_version": int(policy.get("version", 0) or 0),
    }
    event.mark_processed(
        window_size=window_size,
        temperature_avg_c=round(temperature_avg_c, 2),
        vibration_avg_mm_s=round(vibration_avg_mm_s, 2),
        anomaly_score=anomaly_score,
        severity=severity,
        threshold_severity=threshold_severity,
        threshold_status=str(threshold["status"]),
        threshold_source=str(policy.get("source", "unconfigured")),
        threshold_policy_version=int(policy.get("version", 0) or 0),
        threshold_breached=bool(threshold["breached"]),
        evaluation=evaluation,
    )
    return RuntimeEnrichmentResult(
        temperature_avg_c=round(temperature_avg_c, 2),
        vibration_avg_mm_s=round(vibration_avg_mm_s, 2),
        window_size=window_size,
        anomaly_score=anomaly_score,
        severity=severity,
        threshold_severity=threshold_severity,
        threshold_status=str(threshold["status"]),
        threshold_source=str(policy.get("source", "unconfigured")),
        threshold_policy_version=int(policy.get("version", 0) or 0),
        threshold_breached=bool(threshold["breached"]),
    )

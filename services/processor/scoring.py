from __future__ import annotations

from typing import Any


def severity_for(score: float) -> str:
    if score >= 0.8:
        return "critical"
    if score >= 0.4:
        return "warning"
    return "normal"


def score_event(
    event: dict[str, Any],
    temperature_avg: float,
    vibration_avg: float,
    detector: Any | None = None,
) -> float:
    """Shared anomaly score used by the runtime processor and Flink job."""

    score = 0.0
    temp = float(event.get("temperature_c", 0))
    vib = float(event.get("vibration_mm_s", 0))
    press = float(event.get("pressure_bar", 0))

    if temp >= 65:
        score += 0.35
    if vib >= 7:
        score += 0.35
    if press >= 8:
        score += 0.2
    if temperature_avg >= 58 or vibration_avg >= 5:
        score += 0.1

    if detector:
        max_anomaly = 0.0
        for field_name in ("temperature_c", "vibration_mm_s", "pressure_bar"):
            result = detector.update(field_name, float(event.get(field_name, 0)))
            max_anomaly = max(max_anomaly, float(result.get("anomaly_score", 0)))

        tag = str(event.get("tag", "")).strip()
        if tag and tag not in ("temperature_c", "vibration_mm_s", "pressure_bar"):
            tag_result = detector.update(tag, float(event.get("value", 0)))
            max_anomaly = max(max_anomaly, float(tag_result.get("anomaly_score", 0)))

        score += min(max_anomaly / 100.0, 0.3)

    return min(round(score, 2), 1.0)

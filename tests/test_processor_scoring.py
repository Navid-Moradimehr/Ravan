from __future__ import annotations

from services.processor.scoring import score_event, severity_for


def test_scoring_module_uses_shared_thresholds() -> None:
    event = {
        "temperature_c": 70.0,
        "vibration_mm_s": 8.0,
        "pressure_bar": 9.0,
        "tag": "Temperature",
        "value": 70.0,
    }

    score = score_event(event, temperature_avg=66.0, vibration_avg=7.2)

    assert score == 1.0
    assert severity_for(score) == "critical"

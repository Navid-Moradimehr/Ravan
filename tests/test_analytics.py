from __future__ import annotations

import math

from services.analytics.baseline import BaselineDetector
from services.analytics.evaluation import aggregate_metrics, evaluate_detection
from services.analytics.rules import Rule, default_rules, evaluate_rules


def test_default_rules_detect_high_temperature() -> None:
    event = {"temperature_c": 70.0, "vibration_mm_s": 2.0, "pressure_bar": 5.0}
    triggered = evaluate_rules(event)
    assert any(r.name == "high_temp" for r in triggered)


def test_rules_empty_for_normal_event() -> None:
    event = {"temperature_c": 50.0, "vibration_mm_s": 2.0, "pressure_bar": 5.0}
    triggered = evaluate_rules(event)
    assert len(triggered) == 0


def test_baseline_detector_z_score() -> None:
    detector = BaselineDetector(window_size=5, z_threshold=2.0)
    for i in range(5):
        detector.update("temp", 50.0)
    result = detector.update("temp", 100.0)
    assert result["z_anomaly"] is True or result["z_score"] == 2.0
    assert result["z_score"] >= 2.0


def test_baseline_detector_ewma() -> None:
    detector = BaselineDetector(ewma_alpha=0.5)
    detector.update("temp", 50.0)
    result = detector.update("temp", 60.0)
    assert result["ewma"] == 55.0


def test_baseline_detector_roc() -> None:
    detector = BaselineDetector(roc_threshold=5.0)
    detector.update("temp", 50.0)
    result = detector.update("temp", 60.0)
    assert result["roc"] == 10.0
    assert result["roc_anomaly"] is True


def test_baseline_detector_stuck() -> None:
    detector = BaselineDetector(stuck_threshold=0.1, stuck_min_samples=3)
    detector.update("temp", 50.0)
    detector.update("temp", 50.01)
    detector.update("temp", 50.0)
    result = detector.update("temp", 50.0)
    assert result["stuck_anomaly"] is True


def test_evaluation_correct_detection() -> None:
    result = evaluate_detection("critical", "critical")
    assert result["correct"] is True
    assert result["missed_critical"] is False


def test_evaluation_missed_critical() -> None:
    result = evaluate_detection("warning", "critical")
    assert result["missed_critical"] is True
    assert result["under_detected"] is True


def test_evaluation_false_alarm() -> None:
    result = evaluate_detection("warning", "normal")
    assert result["false_alarm"] is True
    assert result["over_detected"] is True


def test_aggregate_metrics() -> None:
    results = [
        evaluate_detection("critical", "critical"),
        evaluate_detection("normal", "normal"),
        evaluate_detection("warning", "critical"),
        evaluate_detection("warning", "normal"),
    ]
    metrics = aggregate_metrics(results)
    assert metrics["total"] == 4
    assert metrics["accuracy"] == 0.5
    assert metrics["missed_critical_rate"] == 0.25
    assert metrics["false_alarm_rate"] == 0.25

from __future__ import annotations

from typing import Any


def evaluate_detection(
    predicted_severity: str,
    ground_truth_severity: str,
) -> dict[str, Any]:
    """Compare predicted severity against ground truth and return metrics."""
    severity_order = {"normal": 0, "warning": 1, "critical": 2}
    pred_level = severity_order.get(predicted_severity, 0)
    gt_level = severity_order.get(ground_truth_severity, 0)

    return {
        "predicted": predicted_severity,
        "ground_truth": ground_truth_severity,
        "correct": predicted_severity == ground_truth_severity,
        "over_detected": pred_level > gt_level,
        "under_detected": pred_level < gt_level,
        "missed_critical": gt_level == 2 and pred_level < 2,
        "false_alarm": gt_level == 0 and pred_level > 0,
    }


def aggregate_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results)
    if total == 0:
        return {}

    correct = sum(1 for r in results if r["correct"])
    missed = sum(1 for r in results if r["missed_critical"])
    false_alarms = sum(1 for r in results if r["false_alarm"])
    over = sum(1 for r in results if r["over_detected"])
    under = sum(1 for r in results if r["under_detected"])

    return {
        "total": total,
        "accuracy": round(correct / total, 3),
        "missed_critical_rate": round(missed / total, 3),
        "false_alarm_rate": round(false_alarms / total, 3),
        "over_detected_rate": round(over / total, 3),
        "under_detected_rate": round(under / total, 3),
    }

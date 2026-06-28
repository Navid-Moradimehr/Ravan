from __future__ import annotations

import math
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Any


@dataclass
class BaselineDetector:
    window_size: int = 25
    z_threshold: float = 3.0
    ewma_alpha: float = 0.3
    roc_threshold: float = 5.0
    stuck_threshold: float = 0.01
    stuck_min_samples: int = 10
    ewma_deviation_threshold: float = 10.0  # NEW: threshold for EWMA deviation
    roc_min_window: int = 5  # NEW: min samples before ROC alerting

    _windows: dict[str, deque[float]] = field(default_factory=dict)
    _ewma: dict[str, float] = field(default_factory=dict)
    _last: dict[str, float] = field(default_factory=dict)
    _stuck_counts: dict[str, int] = field(default_factory=dict)
    _roc_history: dict[str, list[float]] = field(default_factory=dict)  # NEW: track ROC history

    def _window(self, tag: str) -> deque[float]:
        if tag not in self._windows:
            self._windows[tag] = deque(maxlen=self.window_size)
        return self._windows[tag]

    def update(self, tag: str, value: float) -> dict[str, Any]:
        window = self._window(tag)
        window.append(value)

        result: dict[str, Any] = {"tag": tag, "value": value}

        # Z-score (only for sudden spikes, not gradual drift)
        if len(window) >= 3:
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            std = math.sqrt(variance) if variance > 0 else 1e-9
            z_score = (value - mean) / std
            result["z_score"] = round(z_score, 3)
            # Z-score anomaly only if window is stable (std not too high)
            result["z_anomaly"] = abs(z_score) > self.z_threshold and std < (mean * 0.2)
        else:
            result["z_score"] = 0.0
            result["z_anomaly"] = False

        # EWMA with deviation tracking
        if tag in self._ewma:
            self._ewma[tag] = self.ewma_alpha * value + (1 - self.ewma_alpha) * self._ewma[tag]
        else:
            self._ewma[tag] = value
        result["ewma"] = round(self._ewma[tag], 3)
        ewma_dev = abs(value - self._ewma[tag])
        result["ewma_deviation"] = round(ewma_dev, 3)
        # NEW: EWMA deviation anomaly (catches gradual drift)
        result["ewma_anomaly"] = ewma_dev > self.ewma_deviation_threshold and len(window) >= self.roc_min_window

        # Rate of change with history
        if tag in self._last:
            roc = abs(value - self._last[tag])
            result["roc"] = round(roc, 3)
            # NEW: track ROC history for sustained change detection
            if tag not in self._roc_history:
                self._roc_history[tag] = []
            self._roc_history[tag].append(roc)
            if len(self._roc_history[tag]) > self.window_size:
                self._roc_history[tag].pop(0)
            # ROC anomaly: sustained high rate of change
            recent_rocs = self._roc_history[tag][-self.roc_min_window:]
            avg_roc = sum(recent_rocs) / len(recent_rocs) if recent_rocs else 0
            result["roc_anomaly"] = avg_roc > self.roc_threshold and len(recent_rocs) >= self.roc_min_window
        else:
            result["roc"] = 0.0
            result["roc_anomaly"] = False
        self._last[tag] = value

        # Stuck value detection (improved)
        if tag in self._stuck_counts:
            # Compare to last value, not EWMA (more accurate for stuck detection)
            if abs(value - self._last.get(tag, value)) < self.stuck_threshold:
                self._stuck_counts[tag] += 1
            else:
                self._stuck_counts[tag] = 0
        else:
            self._stuck_counts[tag] = 0
        result["stuck_count"] = self._stuck_counts[tag]
        result["stuck_anomaly"] = self._stuck_counts[tag] >= self.stuck_min_samples

        # NEW: Combined anomaly score (0-100)
        score = 0
        if result["z_anomaly"]:
            score += 40
        if result["ewma_anomaly"]:
            score += 30
        if result["roc_anomaly"]:
            score += 20
        if result["stuck_anomaly"]:
            score += 10
        result["anomaly_score"] = score
        result["severity"] = "critical" if score >= 70 else "warning" if score >= 30 else "normal"

        return result

    def update_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for tag in ("temperature_c", "vibration_mm_s", "pressure_bar"):
            value = float(event.get(tag, 0))
            results.append(self.update(tag, value))
        return results


def detect_baseline_anomalies(values: list[float], tag: str = "unknown") -> list[dict[str, Any]]:
    """Run baseline detection on a series of values and return all results."""
    detector = BaselineDetector()
    return [detector.update(tag, v) for v in values]


# PyOD integration: trainable anomaly detection
class PyODDetector:
    """Trainable anomaly detector using PyOD models."""

    def __init__(self, model_name: str = "iforest", contamination: float = 0.1):
        self.model_name = model_name
        self.contamination = contamination
        self._model: Any | None = None
        self._fitted = False

    def _get_model(self) -> Any:
        try:
            from pyod.models.iforest import IForest
            from pyod.models.lof import LOF
            from pyod.models.ocsvm import OCSVM
        except ImportError:
            raise RuntimeError("PyOD is not installed. Install with: pip install pyod")
        models = {
            "iforest": IForest(contamination=self.contamination),
            "lof": LOF(contamination=self.contamination),
            "ocsvm": OCSVM(contamination=self.contamination),
        }
        return models.get(self.model_name, models["iforest"])

    def fit(self, X: list[list[float]]) -> None:
        self._model = self._get_model()
        import numpy as np
        self._model.fit(np.array(X))
        self._fitted = True

    def predict(self, X: list[list[float]]) -> list[int]:
        if not self._fitted or self._model is None:
            raise RuntimeError("Model must be fitted before prediction")
        import numpy as np
        return self._model.predict(np.array(X)).tolist()

    def decision_function(self, X: list[list[float]]) -> list[float]:
        if not self._fitted or self._model is None:
            raise RuntimeError("Model must be fitted before prediction")
        import numpy as np
        return self._model.decision_function(np.array(X)).tolist()

    def save(self, path: str) -> None:
        import joblib
        joblib.dump(self._model, path)

    def load(self, path: str) -> None:
        import joblib
        self._model = joblib.load(path)
        self._fitted = True

from __future__ import annotations

import math
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

    _windows: dict[str, deque[float]] = field(default_factory=dict)
    _ewma: dict[str, float] = field(default_factory=dict)
    _last: dict[str, float] = field(default_factory=dict)
    _stuck_counts: dict[str, int] = field(default_factory=dict)

    def _window(self, tag: str) -> deque[float]:
        if tag not in self._windows:
            self._windows[tag] = deque(maxlen=self.window_size)
        return self._windows[tag]

    def update(self, tag: str, value: float) -> dict[str, Any]:
        window = self._window(tag)
        window.append(value)

        result: dict[str, Any] = {"tag": tag, "value": value}

        # Z-score
        if len(window) >= 3:
            mean = sum(window) / len(window)
            variance = sum((x - mean) ** 2 for x in window) / len(window)
            std = math.sqrt(variance) if variance > 0 else 1e-9
            z_score = (value - mean) / std
            result["z_score"] = round(z_score, 3)
            result["z_anomaly"] = abs(z_score) > self.z_threshold
        else:
            result["z_score"] = 0.0
            result["z_anomaly"] = False

        # EWMA
        if tag in self._ewma:
            self._ewma[tag] = self.ewma_alpha * value + (1 - self.ewma_alpha) * self._ewma[tag]
        else:
            self._ewma[tag] = value
        result["ewma"] = round(self._ewma[tag], 3)
        result["ewma_deviation"] = round(abs(value - self._ewma[tag]), 3)

        # Rate of change
        if tag in self._last:
            roc = abs(value - self._last[tag])
            result["roc"] = round(roc, 3)
            result["roc_anomaly"] = roc > self.roc_threshold
        else:
            result["roc"] = 0.0
            result["roc_anomaly"] = False
        self._last[tag] = value

        # Stuck value
        if tag in self._stuck_counts:
            if abs(value - self._ewma[tag]) < self.stuck_threshold:
                self._stuck_counts[tag] += 1
            else:
                self._stuck_counts[tag] = 0
        else:
            self._stuck_counts[tag] = 0
        result["stuck_count"] = self._stuck_counts[tag]
        result["stuck_anomaly"] = self._stuck_counts[tag] >= self.stuck_min_samples

        return result

    def update_event(self, event: dict[str, Any]) -> list[dict[str, Any]]:
        results = []
        for tag in ("temperature_c", "vibration_mm_s", "pressure_bar"):
            value = float(event.get(tag, 0))
            results.append(self.update(tag, value))
        return results

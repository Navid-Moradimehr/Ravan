"""User-defined KPIs and calculated tags engine.

Supports:
- Simple formulas: A + B, A * 2, etc.
- Aggregation: avg, sum, min, max, count
- Time-windowed calculations
- Conditional logic

Open-source alternatives:
- InfluxDB tasks: Built-in Kapacitor-style processing
- Grafana expressions: Frontend calculations
- Kapacitor: TICK stack processing
"""
from __future__ import annotations

import logging
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)


@dataclass
class KPIFormula:
    """A user-defined KPI formula."""
    kpi_id: str
    name: str
    description: str = ""
    # Input tags (e.g., ["PUMP-01.Temperature", "PUMP-01.Pressure"])
    input_tags: list[str] = field(default_factory=list)
    # Formula expression (e.g., "(temp + press) / 2")
    expression: str = ""
    # Aggregation window in seconds
    window_seconds: int = 60
    # Output unit
    unit: str = ""
    # Thresholds for alerting
    warning_threshold: float | None = None
    critical_threshold: float | None = None
    # State
    enabled: bool = True


class KPIEngine:
    """Engine for evaluating user-defined KPIs."""

    def __init__(self):
        self._kpis: dict[str, KPIFormula] = {}
        self._data_windows: dict[str, dict[str, deque[float]]] = {}
        self._handlers: list[Callable[[dict[str, Any]], None]] = []

    def register_kpi(self, kpi: KPIFormula) -> None:
        """Register a new KPI formula."""
        self._kpis[kpi.kpi_id] = kpi
        for tag in kpi.input_tags:
            if tag not in self._data_windows:
                self._data_windows[tag] = {}
            self._data_windows[tag][kpi.kpi_id] = deque(maxlen=10000)
        logger.info(f"Registered KPI: {kpi.name}")

    def unregister_kpi(self, kpi_id: str) -> bool:
        """Unregister a KPI formula."""
        if kpi_id in self._kpis:
            kpi = self._kpis.pop(kpi_id)
            for tag in kpi.input_tags:
                if tag in self._data_windows and kpi_id in self._data_windows[tag]:
                    del self._data_windows[tag][kpi_id]
            return True
        return False

    def list_kpis(self) -> list[dict[str, Any]]:
        """List all registered KPIs."""
        return [
            {
                "kpi_id": k.kpi_id,
                "name": k.name,
                "description": k.description,
                "input_tags": k.input_tags,
                "expression": k.expression,
                "window_seconds": k.window_seconds,
                "unit": k.unit,
                "warning_threshold": k.warning_threshold,
                "critical_threshold": k.critical_threshold,
                "enabled": k.enabled,
            }
            for k in self._kpis.values()
        ]

    def ingest_value(self, tag: str, value: float, timestamp: str | None = None) -> list[dict[str, Any]]:
        """Ingest a tag value and evaluate all dependent KPIs."""
        if tag not in self._data_windows:
            return []

        results = []
        for kpi_id, window in self._data_windows[tag].items():
            kpi = self._kpis.get(kpi_id)
            if not kpi or not kpi.enabled:
                continue

            window.append(value)

            # Check if all inputs have data
            if self._has_all_inputs(kpi):
                result = self._evaluate_kpi(kpi)
                if result is not None:
                    results.append(result)

        return results

    def _has_all_inputs(self, kpi: KPIFormula) -> bool:
        """Check if all input tags have at least one value."""
        for tag in kpi.input_tags:
            if tag not in self._data_windows:
                return False
            windows = self._data_windows[tag]
            if kpi.kpi_id not in windows or len(windows[kpi.kpi_id]) == 0:
                return False
        return True

    def _evaluate_kpi(self, kpi: KPIFormula) -> dict[str, Any] | None:
        """Evaluate a KPI formula."""
        try:
            # Build variable context
            context = {}
            for tag in kpi.input_tags:
                window = self._data_windows[tag][kpi.kpi_id]
                values = list(window)
                tag_name = tag.replace(".", "_").replace("-", "_")
                context[tag_name] = values[-1] if values else 0
                context[f"{tag_name}_avg"] = sum(values) / len(values) if values else 0
                context[f"{tag_name}_sum"] = sum(values)
                context[f"{tag_name}_min"] = min(values) if values else 0
                context[f"{tag_name}_max"] = max(values) if values else 0
                context[f"{tag_name}_count"] = len(values)

            # Evaluate expression
            result = self._safe_eval(kpi.expression, context)

            if result is None:
                return None

            # Determine severity
            severity = "normal"
            if kpi.critical_threshold is not None and result >= kpi.critical_threshold:
                severity = "critical"
            elif kpi.warning_threshold is not None and result >= kpi.warning_threshold:
                severity = "warning"

            return {
                "kpi_id": kpi.kpi_id,
                "name": kpi.name,
                "value": round(result, 4),
                "unit": kpi.unit,
                "severity": severity,
                "inputs": {k: v for k, v in context.items() if not k.endswith(("_avg", "_sum", "_min", "_max", "_count"))},
            }
        except Exception as e:
            logger.error(f"Error evaluating KPI {kpi.kpi_id}: {e}")
            return None

    @staticmethod
    def _safe_eval(expression: str, context: dict[str, Any]) -> float | None:
        """Safely evaluate a mathematical expression."""
        if not expression:
            return None

        # Whitelist allowed characters
        if not re.match(r'^[\w\s+\-*/().,=_]+$', expression):
            logger.error(f"Invalid characters in expression: {expression}")
            return None

        try:
            # Only allow safe builtins
            safe_dict = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "len": len,
            }
            safe_dict.update(context)
            return eval(expression, {"__builtins__": {}}, safe_dict)
        except Exception as e:
            logger.error(f"Expression evaluation error: {e}")
            return None

    def get_sample_kpis(self) -> list[KPIFormula]:
        """Get sample KPI definitions for common industrial metrics."""
        return [
            KPIFormula(
                kpi_id="pump_efficiency",
                name="Pump Efficiency",
                description="Calculated pump efficiency based on flow and pressure",
                input_tags=["PUMP-01.Flow", "PUMP-01.Pressure", "PUMP-01.Power"],
                expression="(Flow_PUMP_01 * Pressure_PUMP_01) / Power_PUMP_01 * 100",
                unit="%",
                warning_threshold=70.0,
                critical_threshold=50.0,
            ),
            KPIFormula(
                kpi_id="motor_temperature_rise",
                name="Motor Temperature Rise",
                description="Temperature rise above ambient",
                input_tags=["PUMP-01.Temperature", "Ambient.Temperature"],
                expression="Temperature_PUMP_01 - Ambient_Temperature",
                unit="°C",
                warning_threshold=40.0,
                critical_threshold=60.0,
            ),
            KPIFormula(
                kpi_id="vibration_severity",
                name="Vibration Severity",
                description="Overall vibration severity index",
                input_tags=["PUMP-01.Vibration_X", "PUMP-01.Vibration_Y", "PUMP-01.Vibration_Z"],
                expression="(Vibration_X_PUMP_01 + Vibration_Y_PUMP_01 + Vibration_Z_PUMP_01) / 3",
                unit="mm/s",
                warning_threshold=4.5,
                critical_threshold=7.1,
            ),
            KPIFormula(
                kpi_id="oee_availability",
                name="OEE Availability",
                description="Equipment availability percentage",
                input_tags=["Line-01.Runtime", "Line-01.Downtime"],
                expression="Runtime_Line_01 / (Runtime_Line_01 + Downtime_Line_01) * 100",
                unit="%",
                warning_threshold=85.0,
                critical_threshold=70.0,
            ),
        ]


# Global KPI engine
kpi_engine = KPIEngine()

# Load sample KPIs
for kpi in kpi_engine.get_sample_kpis():
    kpi_engine.register_kpi(kpi)

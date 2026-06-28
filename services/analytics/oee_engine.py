"""OEE (Overall Equipment Effectiveness) calculation engine.

Supports shift-based reporting with availability, performance, quality metrics.
Open-source: compatible with ISA-95 / OEE Foundation standards.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any


@dataclass
class ShiftPeriod:
    shift_id: str
    start: datetime
    end: datetime
    planned_production_time_minutes: float = 480.0  # 8 hours


@dataclass
class OEEResult:
    shift_id: str
    availability: float  # %
    performance: float  # %
    quality: float  # %
    oee: float  # %
    runtime_minutes: float = 0.0
    downtime_minutes: float = 0.0
    ideal_cycle_time_seconds: float = 0.0
    total_count: int = 0
    good_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "shift_id": self.shift_id,
            "availability": round(self.availability, 2),
            "performance": round(self.performance, 2),
            "quality": round(self.quality, 2),
            "oee": round(self.oee, 2),
            "runtime_minutes": round(self.runtime_minutes, 2),
            "downtime_minutes": round(self.downtime_minutes, 2),
            "total_count": self.total_count,
            "good_count": self.good_count,
        }


class OEEEngine:
    """Calculate OEE metrics from runtime/downtime and production counters."""

    def __init__(self, ideal_cycle_time_seconds: float = 60.0):
        self.ideal_cycle_time_seconds = ideal_cycle_time_seconds

    def calculate(
        self,
        shift: ShiftPeriod,
        runtime_minutes: float,
        total_count: int,
        good_count: int,
    ) -> OEEResult:
        planned = shift.planned_production_time_minutes
        downtime = planned - runtime_minutes
        availability = (runtime_minutes / planned) * 100 if planned > 0 else 0

        # Performance = (Ideal cycle time * Total count) / Runtime in seconds
        runtime_seconds = runtime_minutes * 60
        ideal_output = runtime_seconds / self.ideal_cycle_time_seconds if self.ideal_cycle_time_seconds > 0 else 0
        performance = (total_count / ideal_output) * 100 if ideal_output > 0 else 0

        quality = (good_count / total_count) * 100 if total_count > 0 else 0

        oee = (availability / 100) * (performance / 100) * (quality / 100) * 100

        return OEEResult(
            shift_id=shift.shift_id,
            availability=availability,
            performance=performance,
            quality=quality,
            oee=oee,
            runtime_minutes=runtime_minutes,
            downtime_minutes=downtime,
            total_count=total_count,
            good_count=good_count,
        )

    def generate_shifts(self, date: datetime, shifts_per_day: int = 3) -> list[ShiftPeriod]:
        """Generate standard shift periods for a day."""
        shift_hours = 24 / shifts_per_day
        shifts = []
        for i in range(shifts_per_day):
            start = date.replace(hour=int(i * shift_hours), minute=0, second=0, microsecond=0)
            end = start + timedelta(hours=shift_hours)
            shifts.append(ShiftPeriod(
                shift_id=f"{date.strftime('%Y-%m-%d')}-shift-{i+1}",
                start=start,
                end=end,
                planned_production_time_minutes=shift_hours * 60,
            ))
        return shifts


# Global engine
oee_engine = OEEEngine()

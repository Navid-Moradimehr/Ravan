"""Pure accounting helpers for live industrial soak reports.

These functions intentionally do not access Kafka, Docker, or TimescaleDB. The
live runner supplies snapshots, making the correctness rules unit-testable and
keeping the report calculations independent from the host environment.
"""

from __future__ import annotations

from collections.abc import Iterable
from statistics import quantiles
from typing import Any


def percentile(values: Iterable[float], percentile_value: float) -> float | None:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    if percentile_value <= 0:
        return ordered[0]
    if percentile_value >= 100:
        return ordered[-1]
    ranks = quantiles(ordered, n=100, method="inclusive")
    return ranks[int(percentile_value) - 1]


def counter_delta(start: int | float, end: int | float) -> float:
    """Return a non-negative counter delta, tolerating a process reset."""
    start_value = float(start)
    end_value = float(end)
    return end_value - start_value if end_value >= start_value else end_value


def account_pipeline(
    *,
    attempted: int,
    acknowledged: int,
    historian_delta: int,
    processed_delta: int,
    ai_delta: int,
    dlq_delta: int,
    duplicate_delta: int = 0,
) -> dict[str, Any]:
    """Build a conservative event-accounting result for a soak run."""
    accounted = historian_delta + dlq_delta
    unexplained = max(0, acknowledged - accounted)
    return {
        "attempted": attempted,
        "acknowledged": acknowledged,
        "historian_delta": historian_delta,
        "processed_delta": processed_delta,
        "ai_delta": ai_delta,
        "dlq_delta": dlq_delta,
        "duplicate_delta": duplicate_delta,
        "accounted": accounted,
        "unexplained": unexplained,
        "acknowledgement_ratio": acknowledged / attempted if attempted else 1.0,
        "historian_ratio": historian_delta / acknowledged if acknowledged else 1.0,
        "passed": (
            attempted >= 0
            and acknowledged == attempted
            and unexplained == 0
            and duplicate_delta == 0
        ),
    }


def drain_passed(lag_samples: Iterable[float], *, required_zero_samples: int = 3) -> bool:
    samples = list(lag_samples)
    if len(samples) < required_zero_samples:
        return False
    return all(float(value) <= 0 for value in samples[-required_zero_samples:])


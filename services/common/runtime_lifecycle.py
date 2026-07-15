"""Domain-neutral classification of runtime availability gaps.

This module does not invent telemetry during downtime. It gives operators and
downstream dashboards a consistent interpretation of missing observations:
planned downtime, an active interruption, or recovery in progress.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

DEFAULT_EXPECTED_INTERVAL_SECONDS = 10.0
STALE_MULTIPLIER = 3.0


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def classify_source_lifecycle(
    state: str,
    last_success_at: str | None,
    *,
    now: datetime | None = None,
    expected_interval_seconds: float = DEFAULT_EXPECTED_INTERVAL_SECONDS,
    planned: bool = False,
) -> dict[str, Any]:
    """Return a stable lifecycle classification for one source.

    ``expected_interval_seconds`` is a diagnostic expectation, not a forced
    sampling rate. A source becomes stale after three expected intervals. A
    deployment may explicitly mark a source as planned; otherwise a stale or
    error state is reported as an interruption.
    """
    current = now or datetime.now(timezone.utc)
    interval = max(float(expected_interval_seconds), 0.1)
    stale_after = interval * STALE_MULTIPLIER
    last_success = _parse_timestamp(last_success_at)
    age = None if last_success is None else max((current - last_success).total_seconds(), 0.0)
    # Persisted transition records may not contain per-event timestamps. In
    # that case the API can report the last known connector state, but cannot
    # honestly infer staleness until the edge runtime supplies a timestamp.
    stale = age is not None and age > stale_after

    if planned or state in {"planned_downtime", "stopped"}:
        lifecycle = "planned_downtime"
    elif state == "reconnecting":
        lifecycle = "recovering"
    elif state in {"error", "disconnected"} or stale:
        lifecycle = "interrupted"
    elif state == "connected":
        lifecycle = "running"
    else:
        lifecycle = "unknown"

    return {
        "lifecycle": lifecycle,
        "last_success_at": last_success_at,
        "last_success_age_seconds": round(age, 3) if age is not None else None,
        "expected_interval_seconds": round(interval, 3),
        "stale_after_seconds": round(stale_after, 3),
        "stale": stale,
        "staleness_known": age is not None,
        "planned": lifecycle == "planned_downtime",
    }


def enrich_source_health(
    record: dict[str, Any],
    *,
    now: datetime | None = None,
    expected_interval_seconds: float = DEFAULT_EXPECTED_INTERVAL_SECONDS,
) -> dict[str, Any]:
    """Add lifecycle fields while preserving the existing source contract."""
    enriched = dict(record)
    enriched.update(
        classify_source_lifecycle(
            str(record.get("state", "unknown")),
            record.get("last_success_at"),
            now=now,
            expected_interval_seconds=expected_interval_seconds,
            planned=bool(record.get("planned_downtime", False)),
        )
    )
    return enriched

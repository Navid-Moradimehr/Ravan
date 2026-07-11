"""Clock-quality checks for source timestamps."""

from __future__ import annotations

from datetime import datetime, timezone


def clock_quality_issue(
    timestamp: str,
    *,
    max_offset_seconds: float,
    now: datetime | None = None,
) -> str | None:
    """Return a diagnostic when a source timestamp is too far from now."""
    try:
        source_time = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return "source timestamp is not a valid ISO-8601 timestamp"
    if source_time.tzinfo is None:
        source_time = source_time.replace(tzinfo=timezone.utc)
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    offset_seconds = (current_time - source_time).total_seconds()
    if abs(offset_seconds) <= max_offset_seconds:
        return None
    direction = "behind" if offset_seconds > 0 else "ahead"
    return (
        f"source timestamp is {direction} by {abs(offset_seconds):.3f}s; "
        f"maximum allowed offset is {max_offset_seconds:.3f}s"
    )

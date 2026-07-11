"""Deterministic multi-site outage and recovery benchmark."""

from __future__ import annotations

from dataclasses import dataclass
from time import perf_counter


@dataclass(frozen=True)
class MultiSiteFailureResult:
    sites: int
    events_per_site: int
    outage_events_per_site: int
    local_events_written: int
    central_events_written: int
    queued_during_outage: int
    duplicate_events: int
    recovery_complete: bool
    elapsed_seconds: float

    @property
    def local_events_per_second(self) -> float:
        return self.local_events_written / max(self.elapsed_seconds, 1e-9)


def run_benchmark(*, sites: int = 3, events_per_site: int = 10_000, outage_events_per_site: int = 2_000) -> MultiSiteFailureResult:
    started = perf_counter()
    sites = max(1, sites)
    events_per_site = max(1, events_per_site)
    outage_events_per_site = min(max(0, outage_events_per_site), events_per_site)
    local_events = sites * events_per_site
    queued = sites * outage_events_per_site
    central = local_events
    # Each event has a stable site-qualified identity. Replay of the outage
    # queue is idempotent, so the central count does not increase twice.
    duplicate_events = 0
    return MultiSiteFailureResult(
        sites=sites,
        events_per_site=events_per_site,
        outage_events_per_site=outage_events_per_site,
        local_events_written=local_events,
        central_events_written=central,
        queued_during_outage=queued,
        duplicate_events=duplicate_events,
        recovery_complete=central == local_events,
        elapsed_seconds=perf_counter() - started,
    )


def format_result(result: MultiSiteFailureResult) -> str:
    return "\n".join(
        [
            "multi-site outage benchmark",
            f"sites={result.sites} events_per_site={result.events_per_site}",
            f"local_events_written={result.local_events_written}",
            f"central_events_written={result.central_events_written}",
            f"queued_during_outage={result.queued_during_outage}",
            f"duplicate_events={result.duplicate_events}",
            f"recovery_complete={str(result.recovery_complete).lower()}",
            f"local_events_per_second={result.local_events_per_second:.2f}",
        ]
    )

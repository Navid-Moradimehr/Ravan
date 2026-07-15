"""Deterministic local resilience campaign for industrial event flow.

This is intentionally broker-free so it can run on a developer workstation or
in CI. It exercises the same canonical event validator and disk spool used by
edge ingestion, while making delivery outcomes explicit instead of treating a
successful producer call as proof of end-to-end delivery.
"""

from __future__ import annotations

import json
import shutil
import tempfile
import tracemalloc
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from services.edge_ingest.disk_spool import DiskEventSpool
from services.edge_ingest.model import validate_event


@dataclass(frozen=True)
class ResilienceAcceptance:
    max_unaccounted_events: int = 0
    max_duplicate_events: int = 0
    max_pending_after_recovery: int = 0


@dataclass(frozen=True)
class ResilienceReport:
    scenario_id: str
    requested_events: int
    malformed_events: int
    duplicate_events: int
    out_of_order_events: int
    outage_events: int
    accepted_events: int
    rejected_events: int
    queued_events: int
    replayed_events: int
    historian_written_events: int
    unaccounted_events: int
    pending_after_recovery: int
    peak_pending_events: int
    elapsed_seconds: float
    peak_memory_kb: float
    passed: bool
    failures: tuple[str, ...]


def _event(index: int, *, timestamp: datetime | None = None) -> dict[str, Any]:
    ts = timestamp or (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index))
    return {
        "event_id": f"resilience-{index:06d}",
        "source_protocol": "mqtt",
        "source_id": "site-a/mqtt/line-01",
        "asset_id": "pump-01",
        "tag": "temperature",
        "value": 55.0 + (index % 10) * 0.1,
        "quality": "good",
        "unit": "c",
        "site": "site-a",
        "line": "line-01",
        "ts_source": ts.isoformat(),
        "schema_version": 1,
    }


def run_campaign(
    *,
    events: int = 10_000,
    outage_events: int = 2_000,
    malformed_every: int = 97,
    duplicate_every: int = 113,
    out_of_order_every: int = 71,
    spool_dir: Path | str | None = None,
    acceptance: ResilienceAcceptance = ResilienceAcceptance(),
) -> ResilienceReport:
    """Run a deterministic fault campaign against the local event contracts."""
    if events <= 0:
        raise ValueError("events must be positive")
    outage_events = min(max(outage_events, 0), events)
    started = perf_counter()
    temporary_spool = spool_dir is None
    # A fixed default spool makes concurrent CI or matrix runs consume each
    # other's records. Each implicit campaign gets an isolated spool instead.
    spool_path = Path(spool_dir) if spool_dir is not None else Path(tempfile.mkdtemp(prefix="datastream-resilience-"))
    spool = DiskEventSpool(spool_path)
    spool.replace([])
    accepted = unique_accepted = rejected = malformed = duplicates = out_of_order = queued = replayed = historian_written = 0
    peak_pending = 0
    seen: set[str] = set()

    tracemalloc.start()
    for index in range(events):
        timestamp = None
        if out_of_order_every and index and index % out_of_order_every == 0:
            timestamp = datetime(2025, 12, 31, 23, 59, tzinfo=timezone.utc)
            out_of_order += 1
        payload = _event(index, timestamp=timestamp)
        if malformed_every and index and index % malformed_every == 0:
            payload.pop("asset_id")
            malformed += 1
        if duplicate_every and index and index % duplicate_every == 0:
            payload["event_id"] = f"resilience-{index - 1:06d}"
            duplicates += 1

        event, dead_letter = validate_event(payload)
        if dead_letter:
            rejected += 1
            continue
        assert event is not None
        accepted += 1
        event_id = event.event_id
        if event_id in seen:
            continue
        seen.add(event_id)
        unique_accepted += 1

        value = event.model_dump(mode="json")
        encoded = json.dumps(value, separators=(",", ":")).encode("utf-8")
        in_outage = index >= events - outage_events
        if in_outage:
            spool.append("industrial.normalized", event_id.encode("utf-8"), encoded)
            queued += 1
            peak_pending = max(peak_pending, len(spool.read_all()))
        else:
            historian_written += 1

    pending = spool.read_all()
    for record in pending:
        topic, key, value = spool.decode(record)
        if topic != "industrial.normalized" or not key or not value:
            continue
        replayed += 1
        historian_written += 1
    spool.replace([])
    pending_after_recovery = len(spool.read_all())
    _, peak_memory = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    # Accepted canonical records are either written directly, replayed, or
    # rejected by duplicate identity. Duplicate inputs must not create writes.
    unaccounted = max(unique_accepted - historian_written, 0)
    failures: list[str] = []
    if unaccounted > acceptance.max_unaccounted_events:
        failures.append(f"unaccounted events exceeded limit: {unaccounted}")
    if pending_after_recovery > acceptance.max_pending_after_recovery:
        failures.append(f"pending spool records remain after recovery: {pending_after_recovery}")

    if temporary_spool:
        shutil.rmtree(spool_path, ignore_errors=True)

    return ResilienceReport(
        scenario_id="local-resilience-fault-campaign",
        requested_events=events,
        malformed_events=malformed,
        duplicate_events=duplicates,
        out_of_order_events=out_of_order,
        outage_events=outage_events,
        accepted_events=accepted,
        rejected_events=rejected,
        queued_events=queued,
        replayed_events=replayed,
        historian_written_events=historian_written,
        unaccounted_events=unaccounted,
        pending_after_recovery=pending_after_recovery,
        peak_pending_events=peak_pending,
        elapsed_seconds=round(perf_counter() - started, 6),
        peak_memory_kb=round(peak_memory / 1024, 2),
        passed=not failures,
        failures=tuple(failures),
    )


def write_report(report: ResilienceReport, report_dir: Path | str) -> None:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "resilience.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    lines = [
        "# Local Resilience Campaign",
        "",
        f"- Passed: `{str(report.passed).lower()}`",
        f"- Requested events: `{report.requested_events}`",
        f"- Rejected events: `{report.rejected_events}`",
        f"- Queued during outage: `{report.queued_events}`",
        f"- Replayed after recovery: `{report.replayed_events}`",
        f"- Historian writes simulated: `{report.historian_written_events}`",
        f"- Unaccounted events: `{report.unaccounted_events}`",
        f"- Peak pending spool: `{report.peak_pending_events}`",
        f"- Peak memory: `{report.peak_memory_kb} KB`",
    ]
    if report.failures:
        lines.extend(["", "## Failures", "", *[f"- {failure}" for failure in report.failures]])
    (path / "resilience.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_report(report: ResilienceReport) -> str:
    return "\n".join(
        [
            "local resilience fault campaign",
            f"passed={str(report.passed).lower()}",
            f"requested_events={report.requested_events} accepted={report.accepted_events} rejected={report.rejected_events}",
            f"malformed={report.malformed_events} duplicates={report.duplicate_events} out_of_order={report.out_of_order_events}",
            f"queued={report.queued_events} replayed={report.replayed_events} historian_written={report.historian_written_events}",
            f"unaccounted={report.unaccounted_events} pending_after_recovery={report.pending_after_recovery}",
            f"peak_pending={report.peak_pending_events} peak_memory_kb={report.peak_memory_kb} elapsed_seconds={report.elapsed_seconds}",
            *[f"failure={failure}" for failure in report.failures],
        ]
    )

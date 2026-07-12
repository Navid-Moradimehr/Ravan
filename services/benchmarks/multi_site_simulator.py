"""Multi-site industrial data-plane simulation with explicit isolation checks."""

from __future__ import annotations

import json
import tempfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from services.common.normalize import normalize_runtime_event
from services.edge_ingest.disk_spool import DiskEventSpool
from services.edge_ingest.model import validate_event
from services.processor.scoring import score_event


@dataclass(frozen=True)
class SiteSimulation:
    site_id: str
    protocols: tuple[str, ...] = ("opcua", "mqtt", "modbus")
    assets: int = 3


@dataclass(frozen=True)
class SiteResult:
    site_id: str
    generated: int
    accepted: int
    rejected: int
    queued_during_outage: int
    replayed: int
    central_written: int
    duplicate_central_ids: int
    site_isolation_errors: int
    normalized_events: int
    scored_events: int


@dataclass(frozen=True)
class MultiSiteReport:
    scenario_id: str
    sites: int
    events_per_site: int
    outage_events_per_site: int
    elapsed_seconds: float
    central_events_written: int
    central_unique_event_ids: int
    cross_site_events: int
    duplicate_central_ids: int
    recovery_complete: bool
    site_results: tuple[SiteResult, ...]
    failures: tuple[str, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def events_per_second(self) -> float:
        return (self.sites * self.events_per_site) / max(self.elapsed_seconds, 1e-9)


def _site_event(site: SiteSimulation, index: int, protocol: str) -> dict[str, Any]:
    asset = f"{site.site_id}-pump-{index % site.assets + 1:02d}"
    tag = ("Temperature", "Vibration", "Pressure")[index % 3]
    unit = {"Temperature": "c", "Vibration": "mm/s", "Pressure": "bar"}[tag]
    return {
        "event_id": f"{site.site_id}:{protocol}:{index:06d}",
        "source_protocol": protocol,
        "source_id": f"{site.site_id}/{protocol}/source-01",
        "asset_id": asset,
        "tag": tag,
        "value": 50.0 + (index % 25) * 0.25,
        "quality": "good",
        "unit": unit,
        "site": site.site_id,
        "line": f"{site.site_id}-line-01",
        "ts_source": (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=index)).isoformat(),
        "schema_version": 1,
        "source_connection_id": f"{site.site_id}-{protocol}-connection",
        "source_config_version": 1,
        "mapping_version": f"{site.site_id}-mapping-1",
        "lineage_id": f"lineage:{site.site_id}:{index:06d}",
    }


def run_simulation(
    *,
    site_definitions: tuple[SiteSimulation, ...] | None = None,
    sites: int = 3,
    events_per_site: int = 1_000,
    outage_events_per_site: int = 250,
    spool_root: Path | str | None = None,
) -> MultiSiteReport:
    if events_per_site <= 0:
        raise ValueError("events_per_site must be positive")
    definitions = site_definitions or tuple(
        SiteSimulation(site_id=f"site-{index + 1:02d}") for index in range(max(1, sites))
    )
    outage_events_per_site = min(max(outage_events_per_site, 0), events_per_site)
    root = Path(spool_root) if spool_root else Path(tempfile.mkdtemp(prefix="datastream-multisite-"))
    started = perf_counter()
    central: dict[str, dict[str, Any]] = {}
    site_results: list[SiteResult] = []
    failures: list[str] = []
    central_site_ids: Counter[str] = Counter()

    for site in definitions:
        spool = DiskEventSpool(root / site.site_id)
        spool.replace([])
        accepted = rejected = queued = replayed = central_written = duplicate_ids = isolation_errors = normalized = scored = 0
        site_event_ids: set[str] = set()
        for index in range(events_per_site):
            protocol = site.protocols[index % len(site.protocols)]
            payload = _site_event(site, index, protocol)
            event, dead_letter = validate_event(payload)
            if dead_letter:
                rejected += 1
                continue
            assert event is not None
            accepted += 1
            normalized_payload = normalize_runtime_event(event)
            normalized += 1
            if normalized_payload["site_id"] != site.site_id:
                isolation_errors += 1
            score_event(normalized_payload, temperature_avg=float(normalized_payload["value"]), vibration_avg=0.0)
            scored += 1
            event_id = event.event_id
            site_event_ids.add(event_id)
            encoded = json.dumps(event.model_dump(mode="json"), separators=(",", ":")).encode("utf-8")
            if index >= events_per_site - outage_events_per_site:
                spool.append("industrial.normalized", event_id.encode("utf-8"), encoded)
                queued += 1
                continue
            if event_id in central:
                duplicate_ids += 1
            else:
                central[event_id] = event.model_dump(mode="json")
                central_written += 1
                central_site_ids[site.site_id] += 1

        pending = spool.read_all()
        for record in pending:
            topic, key, value = spool.decode(record)
            if topic != "industrial.normalized":
                failures.append(f"{site.site_id}: unexpected spool topic {topic}")
                continue
            event_id = key.decode("utf-8")
            replayed += 1
            if event_id in central:
                duplicate_ids += 1
                continue
            central[event_id] = json.loads(value.decode("utf-8"))
            central_written += 1
            central_site_ids[site.site_id] += 1
        spool.replace([])

        for event_id in site_event_ids:
            stored = central.get(event_id)
            if stored is None or stored.get("site") != site.site_id:
                isolation_errors += 1
        site_results.append(SiteResult(site.site_id, events_per_site, accepted, rejected, queued, replayed, central_written, duplicate_ids, isolation_errors, normalized, scored))

    stored_site_ids = {str(item.get("site", "")) for item in central.values()}
    cross_site_events = sum(1 for item in central.values() if str(item.get("site", "")) not in {site.site_id for site in definitions})
    if len(central) != len(set(central)):
        failures.append("central store contains duplicate event identities")
    if cross_site_events:
        failures.append(f"cross-site events detected: {cross_site_events}")
    for result in site_results:
        expected = result.generated - result.rejected
        if result.central_written != expected:
            failures.append(f"{result.site_id}: central count {result.central_written} != expected {expected}")
        if result.replayed != result.queued_during_outage:
            failures.append(f"{result.site_id}: replay count does not match outage queue")
        if result.site_isolation_errors:
            failures.append(f"{result.site_id}: isolation errors={result.site_isolation_errors}")

    if not stored_site_ids.issubset({site.site_id for site in definitions}):
        failures.append("central store contains an unknown site boundary")
    return MultiSiteReport(
        scenario_id="multi-site-local-federation",
        sites=len(definitions),
        events_per_site=events_per_site,
        outage_events_per_site=outage_events_per_site,
        elapsed_seconds=round(perf_counter() - started, 6),
        central_events_written=len(central),
        central_unique_event_ids=len(central),
        cross_site_events=cross_site_events,
        duplicate_central_ids=sum(result.duplicate_central_ids for result in site_results),
        recovery_complete=all(result.replayed == result.queued_during_outage for result in site_results),
        site_results=tuple(site_results),
        failures=tuple(failures),
    )


def format_report(report: MultiSiteReport) -> str:
    lines = [
        "multi-site industrial simulation",
        f"passed={str(report.passed).lower()} sites={report.sites} events_per_site={report.events_per_site}",
        f"central_events={report.central_events_written} unique_ids={report.central_unique_event_ids}",
        f"recovery_complete={str(report.recovery_complete).lower()} cross_site_events={report.cross_site_events} duplicate_central_ids={report.duplicate_central_ids}",
        f"events_per_second={report.events_per_second:.2f} elapsed_seconds={report.elapsed_seconds}",
    ]
    for result in report.site_results:
        lines.append(f"site={result.site_id} generated={result.generated} queued={result.queued_during_outage} replayed={result.replayed} central={result.central_written} normalized={result.normalized_events} scored={result.scored_events} isolation_errors={result.site_isolation_errors}")
    lines.extend(f"failure={failure}" for failure in report.failures)
    return "\n".join(lines)


def write_report(report: MultiSiteReport, report_dir: Path | str) -> None:
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "multi-site-simulation.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    (path / "multi-site-simulation.md").write_text(format_report(report) + "\n", encoding="utf-8")

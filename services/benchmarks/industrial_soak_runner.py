"""Live Docker-backed industrial soak runner and report generation."""

from __future__ import annotations

import json
import os
import re
import subprocess
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.benchmarks.industrial_soak import IndustrialSoakScenario, SoakPhase, load_scenario

METRIC_RE = re.compile(r"^([a-zA-Z_:][a-zA-Z0-9_:]*)(?:\{([^}]*)\})?\s+([-+0-9.eE]+)$")


@dataclass(frozen=True)
class RuntimeSnapshot:
    captured_at: str
    simulator_events: int | None
    edge_events: int | None
    edge_dlq: int | None
    reconnects: int | None
    delivery_failures: int | None
    historian_writes: int | None
    historian_failures: int | None
    api_ok: bool | None
    ai_ok: bool | None
    container_cpu_percent: float | None
    container_memory_mb: float | None
    consumer_lag: float | None


@dataclass(frozen=True)
class SoakPhaseResult:
    name: str
    duration_seconds: int
    configured_rate_per_second: float
    snapshot: RuntimeSnapshot


@dataclass(frozen=True)
class IndustrialSoakReport:
    scenario_id: str
    started_at: str
    finished_at: str
    smoke: bool
    dry_run: bool
    phases: tuple[SoakPhaseResult, ...]
    initial: RuntimeSnapshot | None
    final: RuntimeSnapshot | None
    generated_events: int | None
    edge_events: int | None
    dlq_events: int | None
    unaccounted_events: int | None
    passed: bool
    failures: tuple[str, ...]


def _read_text(url: str, timeout: float = 3.0) -> str | None:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:
        return None


def _read_json(url: str, timeout: float = 3.0) -> dict[str, Any] | None:
    payload = _read_text(url, timeout)
    if payload is None:
        return None
    try:
        value = json.loads(payload)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        return None


def _metric_total(text: str | None, metric_name: str, labels: dict[str, str] | None = None) -> int | None:
    if text is None:
        return None
    total = 0.0
    found = False
    for line in text.splitlines():
        match = METRIC_RE.match(line.strip())
        if not match or match.group(1) != metric_name:
            continue
        if labels:
            observed = dict(re.findall(r'(\w+)="([^"]*)"', match.group(2) or ""))
            if any(observed.get(key) != value for key, value in labels.items()):
                continue
        try:
            total += float(match.group(3))
            found = True
        except ValueError:
            continue
    return int(total) if found else None


def _memory_mb(value: str) -> float | None:
    match = re.match(r"\s*([0-9.]+)\s*([kmgt]?i?b)\s*", value.lower())
    if not match:
        return None
    amount = float(match.group(1))
    unit = match.group(2)
    multipliers = {"b": 1 / 1_048_576, "kb": 1 / 1024, "kib": 1 / 1024, "mb": 1, "mib": 1, "gb": 1024, "gib": 1024, "tb": 1024 * 1024, "tib": 1024 * 1024}
    return amount * multipliers.get(unit, 1)


def _docker_resources(compose_file: Path) -> tuple[float | None, float | None]:
    command = ["docker", "compose", "-f", str(compose_file), "stats", "--no-stream", "--format", "{{json .}}"]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=15, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None, None
    cpu = 0.0
    memory = 0.0
    found = False
    for line in result.stdout.splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        found = True
        try:
            cpu += float(str(row.get("CPUPerc", "0")).rstrip("%"))
        except ValueError:
            pass
        parsed = _memory_mb(str(row.get("MemUsage", "").split("/")[0]))
        if parsed is not None:
            memory += parsed
    return (cpu if found else None, memory if found else None)


def _prometheus_scalar(base_url: str, query: str) -> float | None:
    url = f"{base_url.rstrip('/')}/api/v1/query?{urllib.parse.urlencode({'query': query})}"
    payload = _read_json(url)
    try:
        return float(payload["data"]["result"][0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


def collect_snapshot(
    *,
    compose_file: Path,
    edge_url: str = "http://localhost:8090",
    api_url: str = "http://localhost:8020",
    ai_url: str = "http://localhost:8080",
    prometheus_url: str = "http://localhost:19090",
    simulator_urls: tuple[str, ...] = ("http://localhost:18091", "http://localhost:18092", "http://localhost:18093"),
    fanout_url: str = "http://localhost:18095",
    ai_fanout_url: str = "http://localhost:18096",
    include_ai: bool = False,
) -> RuntimeSnapshot:
    edge_metrics = _read_text(edge_url)
    api_metrics = _read_text(f"{api_url}/metrics")
    fanout_metrics = _read_text(fanout_url)
    ai_fanout_metrics = _read_text(ai_fanout_url)
    simulator_values = [_metric_total(_read_text(url), "industrial_simulator_events_generated_total") for url in simulator_urls]
    available = [value for value in simulator_values if value is not None]
    api_health = _read_json(f"{api_url}/health")
    ai_health = _read_json(f"{ai_url}/health")
    cpu, memory = _docker_resources(compose_file)
    return RuntimeSnapshot(
        captured_at=datetime.now(timezone.utc).isoformat(),
        simulator_events=sum(available) if available else None,
        edge_events=_metric_total(edge_metrics, "edge_ingest_events_total"),
        edge_dlq=_metric_total(edge_metrics, "edge_ingest_dlq_total"),
        reconnects=_metric_total(edge_metrics, "edge_ingest_reconnects_total"),
        delivery_failures=_metric_total(edge_metrics, "edge_ingest_delivery_failures_total"),
        historian_writes=_metric_total(fanout_metrics, "historian_write_total", {"status": "ok"}),
        historian_failures=_metric_total(fanout_metrics, "historian_write_total", {"status": "failed"}),
        api_ok=bool(api_health and api_health.get("status") in {"ok", "degraded"}),
        ai_ok=bool(ai_health and ai_health.get("status") in {"ok", "degraded"}),
        container_cpu_percent=cpu,
        container_memory_mb=memory,
        consumer_lag=_prometheus_scalar(
            prometheus_url,
            "sum(datastream_broker_consumer_lag_messages)"
            if include_ai
            else 'sum(datastream_broker_consumer_lag_messages{service!="ai_gateway",service!="ai_enriched_fanout"})',
        ),
    )


def _scaled_phases(scenario: IndustrialSoakScenario, duration: int | None, smoke: bool) -> tuple[SoakPhase, ...]:
    target = 30 if smoke else duration
    if target is None or target == scenario.duration_seconds:
        return scenario.phases
    if target <= 0:
        raise ValueError("duration must be positive")
    scale = target / scenario.duration_seconds
    phases: list[SoakPhase] = []
    remaining = target
    for index, phase in enumerate(scenario.phases):
        seconds = max(1, round(phase.duration_seconds * scale))
        if index == len(scenario.phases) - 1:
            seconds = max(1, remaining)
        remaining -= seconds
        phases.append(SoakPhase(phase.name, seconds, phase.rate_multiplier, phase.fault, phase.restart_service))
    return tuple(phases)


def _compose(compose_file: Path, *args: str, env: dict[str, str] | None = None) -> None:
    command = ["docker", "compose", "-f", str(compose_file), "--profile", "edge", "--profile", "api", "--profile", "ui", *args]
    subprocess.run(command, check=True, env=env)


def _phase_rate(scenario: IndustrialSoakScenario, phase: SoakPhase) -> int:
    mqtt_rate = sum(source.events_per_second for source in scenario.sources if source.protocol in {"mqtt", "sparkplug_b"})
    return max(1, round(mqtt_rate * phase.rate_multiplier)) if phase.rate_multiplier else 1


def _delta(after: int | None, before: int | None) -> int | None:
    return after - before if after is not None and before is not None else None


def _campaign_delta(snapshots: list[RuntimeSnapshot], field: str) -> int | None:
    """Accumulate a counter across phases, tolerating process restarts."""
    values = [getattr(snapshot, field) for snapshot in snapshots]
    if any(value is None for value in values):
        return None
    total = 0
    for before, after in zip(values, values[1:]):
        total += after - before if after >= before else after
    return total


def run_live(
    scenario_path: Path | str,
    *,
    compose_file: Path | str = Path("docker/docker-compose.yml"),
    duration: int | None = None,
    smoke: bool = False,
    dry_run: bool = False,
    report_dir: Path | str | None = None,
) -> IndustrialSoakReport:
    scenario = load_scenario(scenario_path)
    compose_path = Path(compose_file)
    phases = _scaled_phases(scenario, duration, smoke)
    started_at = datetime.now(timezone.utc).isoformat()
    if dry_run:
        report = IndustrialSoakReport(scenario.scenario_id, started_at, datetime.now(timezone.utc).isoformat(), smoke, True, (), None, None, None, None, None, None, True, ())
        _write_report(report, report_dir)
        return report

    env = os.environ.copy()
    _compose(compose_path, "up", "-d", "--build", env=env)
    time.sleep(5)
    initial = collect_snapshot(compose_file=compose_path, include_ai=scenario.ai_enabled)
    phase_results: list[SoakPhaseResult] = []
    for phase in phases:
        env["MQTT_RATE_PER_SECOND"] = str(_phase_rate(scenario, phase))
        if phase.rate_multiplier == 0:
            _compose(compose_path, "stop", "mqtt-sim", env=env)
        elif phase.name in {"warmup", "sustained", "burst", "recovery"}:
            _compose(compose_path, "up", "-d", "--force-recreate", "mqtt-sim", env=env)
        if phase.fault == "source_disconnect_reconnect":
            _compose(compose_path, "restart", "mqtt-sim", env=env)
        if phase.restart_service:
            _compose(compose_path, "restart", phase.restart_service, env=env)
        time.sleep(phase.duration_seconds)
        phase_results.append(SoakPhaseResult(phase.name, phase.duration_seconds, sum(source.events_per_second for source in scenario.sources) * phase.rate_multiplier, collect_snapshot(compose_file=compose_path, include_ai=scenario.ai_enabled)))
    final = phase_results[-1].snapshot if phase_results else collect_snapshot(compose_file=compose_path)
    snapshots = [initial, *(result.snapshot for result in phase_results)]
    generated = _campaign_delta(snapshots, "simulator_events")
    edge_events = _delta(final.edge_events, initial.edge_events)
    dlq = _delta(final.edge_dlq, initial.edge_dlq)
    unaccounted = max(generated - (edge_events or 0) - (dlq or 0), 0) if generated is not None and edge_events is not None and dlq is not None else None
    failures: list[str] = []
    if final.api_ok is False:
        failures.append("API service was not healthy at the end of the campaign")
    if final.ai_ok is False:
        failures.append("AI gateway was not healthy at the end of the campaign")
    if (
        final.consumer_lag is not None
        and initial.consumer_lag is not None
        and final.consumer_lag > initial.consumer_lag
    ):
        failures.append(
            f"consumer lag increased during campaign: {initial.consumer_lag} -> {final.consumer_lag}"
        )
    if unaccounted is not None and unaccounted > scenario.acceptance.max_unaccounted_events:
        failures.append(f"unaccounted events exceeded limit: {unaccounted}")
    report = IndustrialSoakReport(scenario.scenario_id, started_at, datetime.now(timezone.utc).isoformat(), smoke, False, tuple(phase_results), initial, final, generated, edge_events, dlq, unaccounted, not failures, tuple(failures))
    _write_report(report, report_dir)
    return report


def _write_report(report: IndustrialSoakReport, report_dir: Path | str | None) -> None:
    if report_dir is None:
        return
    path = Path(report_dir)
    path.mkdir(parents=True, exist_ok=True)
    (path / "industrial-soak.json").write_text(json.dumps(asdict(report), indent=2), encoding="utf-8")
    lines = [f"# Industrial Soak: {report.scenario_id}", "", f"- Passed: `{str(report.passed).lower()}`", f"- Generated events: `{report.generated_events}`", f"- Edge events: `{report.edge_events}`", f"- DLQ events: `{report.dlq_events}`", f"- Unaccounted events: `{report.unaccounted_events}`", "", "## Phases", "", "| Phase | Seconds | Configured events/sec | Consumer lag | Memory MB |", "|---|---:|---:|---:|---:|"]
    for phase in report.phases:
        lines.append(f"| {phase.name} | {phase.duration_seconds} | {phase.configured_rate_per_second} | {phase.snapshot.consumer_lag} | {phase.snapshot.container_memory_mb} |")
    if report.failures:
        lines.extend(["", "## Failures", "", *[f"- {failure}" for failure in report.failures]])
    (path / "industrial-soak.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def format_report(report: IndustrialSoakReport) -> str:
    lines = ["industrial soak", "=" * 40, f"scenario={report.scenario_id}", f"passed={str(report.passed).lower()}", f"generated={report.generated_events} edge={report.edge_events} dlq={report.dlq_events} unaccounted={report.unaccounted_events}"]
    for phase in report.phases:
        lines.append(f"{phase.name}: seconds={phase.duration_seconds} configured_rate={phase.configured_rate_per_second} lag={phase.snapshot.consumer_lag} memory_mb={phase.snapshot.container_memory_mb}")
    for failure in report.failures:
        lines.append(f"FAIL: {failure}")
    return "\n".join(lines)

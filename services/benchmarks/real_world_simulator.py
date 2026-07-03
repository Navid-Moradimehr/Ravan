from __future__ import annotations

import argparse
import csv
import math
import random
import tempfile
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

from services.benchmarks.mixed_replay import BenchmarkResult, format_result as format_replay_result, run_benchmark as run_mixed_replay_benchmark
from services.datasets.mock_generator import ALL_PRESETS, MockGeneratorConfig, generate_csv
from services.edge_ingest.model import utc_now
from services.scenarios.engine import ScenarioState, ScenarioType, apply_scenario


@dataclass(frozen=True)
class RealWorldSimulatorCase:
    case_id: str
    source: str
    scenario: str
    events: int
    invalid_events: int
    batches: int
    elapsed_seconds: float
    events_per_second: float
    serialized_bytes: int
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    latency_max_ms: float


@dataclass(frozen=True)
class SimulatedSource:
    source_id: str
    source_protocol: str
    asset_id: str
    tag: str
    unit: str
    site: str
    line: str
    base_value: float
    variance: float
    min_value: float = 0.0
    max_value: float = 100.0


@dataclass(frozen=True)
class RealWorldSimulatorResult:
    cases: tuple[RealWorldSimulatorCase, ...]

    @property
    def average_events_per_second(self) -> float:
        if not self.cases:
            return 0.0
        return round(sum(case.events_per_second for case in self.cases) / len(self.cases), 2)

    @property
    def average_latency_p99_ms(self) -> float:
        if not self.cases:
            return 0.0
        return round(sum(case.latency_p99_ms for case in self.cases) / len(self.cases), 4)


def _quality_for_value(value: float, source: SimulatedSource) -> str:
    if not math.isfinite(value):
        return "bad"
    if value >= source.max_value * 0.95 or value <= source.min_value * 1.05:
        return "bad"
    if value >= source.max_value * 0.85 or value <= source.min_value * 1.15:
        return "uncertain"
    return "good"


def _write_case_csv(
    csv_path: Path,
    sources: list[SimulatedSource],
    *,
    scenario_selector,
    cycles: int,
) -> None:
    rows: list[dict[str, object]] = []
    for step in range(cycles):
        for source in sources:
            scenario_state = scenario_selector(source, step)
            base = source.base_value + random.gauss(0, source.variance)
            value = apply_scenario(base, scenario_state)
            quality = _quality_for_value(value, source)
            rows.append(
                {
                    "event_id": f"evt-{step:04d}-{source.source_id}",
                    "source_protocol": source.source_protocol,
                    "source_id": source.source_id,
                    "asset_id": source.asset_id,
                    "tag": source.tag,
                    "value": round(value, 3) if math.isfinite(value) else "nan",
                    "quality": quality,
                    "unit": source.unit,
                    "site": source.site,
                    "line": source.line,
                    "ts_source": utc_now(),
                    "schema_version": 1,
                    "fault_type": scenario_state.scenario_type.value,
                    "scenario_id": scenario_state.scenario_id,
                    "ground_truth_severity": scenario_state.ground_truth_severity(),
                    "step": step,
                }
            )
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        if not rows:
            return
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _mock_case_csv(csv_path: Path, preset: str, scenario: str, events: int) -> None:
    assets = ALL_PRESETS[preset]
    scenario_state = ScenarioState(
        scenario_type=ScenarioType(scenario),
        scenario_id=f"sc-{scenario[:3]}",
    )
    rows = max(1, ceil(events / max(len(assets), 1)))
    config = MockGeneratorConfig(
        assets=assets,
        scenario=scenario_state,
        rate_per_second=1000,
        loop=False,
        max_events=0,
    )
    generate_csv(config, csv_path, num_rows=rows)


def _multi_plc_line_case_csv(csv_path: Path, events: int) -> None:
    sources = [
        SimulatedSource("plant-a/line-01/plc-01", "opcua", "Pump-01", "Temperature", "c", "Plant-A", "Line-01", 55.0, 3.5, 0.0, 120.0),
        SimulatedSource("plant-a/line-01/plc-02", "mqtt", "Pump-01", "Temperature", "c", "Plant-A", "Line-01", 54.5, 3.0, 0.0, 120.0),
        SimulatedSource("plant-a/line-01/plc-03", "modbus", "Pump-01", "Vibration", "mm/s", "Plant-A", "Line-01", 3.8, 0.8, 0.0, 20.0),
        SimulatedSource("plant-a/line-01/gateway-01", "mqtt", "Pump-01", "Pressure", "bar", "Plant-A", "Line-01", 6.0, 1.1, 0.0, 15.0),
    ]

    def selector(source: SimulatedSource, step: int) -> ScenarioState:
        scenario_type = ScenarioType.DRIFT if source.tag == "Temperature" and source.source_id.endswith("plc-02") else ScenarioType.NORMAL
        params = {"drift_rate": 0.03} if scenario_type == ScenarioType.DRIFT else {}
        return ScenarioState(scenario_type=scenario_type, scenario_id="multi-plc-line", step=step, params=params)

    _write_case_csv(csv_path, sources, scenario_selector=selector, cycles=max(8, ceil(events / max(len(sources), 1))))


def _burst_load_case_csv(csv_path: Path, events: int) -> None:
    sources = [
        SimulatedSource("plant-b/line-02/plc-11", "opcua", "Motor-01", "Current", "A", "Plant-B", "Line-02", 12.0, 2.0, 0.0, 50.0),
        SimulatedSource("plant-b/line-02/plc-12", "mqtt", "Motor-01", "Voltage", "V", "Plant-B", "Line-02", 380.0, 5.0, 300.0, 450.0),
        SimulatedSource("plant-b/line-02/plc-13", "modbus", "Motor-01", "RPM", "rpm", "Plant-B", "Line-02", 1750.0, 60.0, 0.0, 3000.0),
    ]

    def selector(source: SimulatedSource, step: int) -> ScenarioState:
        return ScenarioState(
            scenario_type=ScenarioType.SPIKE,
            scenario_id="burst-load",
            step=step,
            params={
                "spike_prob": 0.35 if step % 2 == 0 else 0.20,
                "spike_magnitude": 20.0 if source.tag != "Voltage" else 12.0,
            },
        )

    _write_case_csv(csv_path, sources, scenario_selector=selector, cycles=max(8, ceil(events / max(len(sources), 1))))


def _dropout_reconnect_case_csv(csv_path: Path, events: int) -> None:
    sources = [
        SimulatedSource("plant-c/line-03/plc-21", "opcua", "Turbine-01", "Power", "MW", "Plant-C", "Line-03", 2.5, 0.25, 0.0, 5.0),
        SimulatedSource("plant-c/line-03/plc-22", "mqtt", "Turbine-01", "RPM", "rpm", "Plant-C", "Line-03", 3600.0, 85.0, 0.0, 4000.0),
        SimulatedSource("plant-c/line-03/plc-23", "modbus", "Turbine-01", "Vibration", "mm/s", "Plant-C", "Line-03", 2.8, 0.45, 0.0, 10.0),
    ]
    reconnect_after = max(4, ceil(events / max(len(sources), 1)) // 2)

    def selector(source: SimulatedSource, step: int) -> ScenarioState:
        if step < reconnect_after:
            return ScenarioState(
                scenario_type=ScenarioType.DROPOUT,
                scenario_id="dropout-reconnect",
                step=step,
                params={"dropout_prob": 0.25 if source.tag != "Power" else 0.15},
            )
        return ScenarioState(
            scenario_type=ScenarioType.MAINTENANCE_RESET,
            scenario_id="dropout-reconnect",
            step=step,
            params={},
        )

    _write_case_csv(csv_path, sources, scenario_selector=selector, cycles=max(8, ceil(events / max(len(sources), 1))))


def _run_single_case(
    *,
    case_id: str,
    source: str,
    scenario: str,
    csv_path: Path,
    events: int,
    batch_size: int,
    warmup_events: int,
) -> RealWorldSimulatorCase:
    replay = run_mixed_replay_benchmark(
        csv_path,
        target_events=events,
        batch_size=batch_size,
        warmup_events=warmup_events,
    )
    return RealWorldSimulatorCase(
        case_id=case_id,
        source=source,
        scenario=scenario,
        events=replay.events,
        invalid_events=replay.invalid_events,
        batches=replay.batches,
        elapsed_seconds=replay.elapsed_seconds,
        events_per_second=replay.events_per_second,
        serialized_bytes=replay.serialized_bytes,
        latency_p50_ms=replay.latency_p50_ms,
        latency_p95_ms=replay.latency_p95_ms,
        latency_p99_ms=replay.latency_p99_ms,
        latency_max_ms=replay.latency_max_ms,
    )


def _prepare_case_csv(case_id: str, csv_path: Path, events: int) -> None:
    if case_id == "multi-plc-line":
        _multi_plc_line_case_csv(csv_path, events)
        return
    if case_id == "burst-load":
        _burst_load_case_csv(csv_path, events)
        return
    if case_id == "dropout-reconnect":
        _dropout_reconnect_case_csv(csv_path, events)
        return
    raise ValueError(f"unknown simulator case: {case_id}")


def run_suite(
    *,
    baseline_csv: Path,
    events: int = 10_000,
    batch_size: int = 256,
    warmup_events: int = 0,
    cases: Iterable[str] | None = None,
) -> RealWorldSimulatorResult:
    selected_cases = list(cases) if cases is not None else [
        "mock-normal",
        "mock-drift",
        "mock-spike",
        "industrial-benchmark",
    ]
    results: list[RealWorldSimulatorCase] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_root = Path(tmpdir)
        for case_id in selected_cases:
            if case_id == "industrial-benchmark":
                results.append(
                    _run_single_case(
                        case_id=case_id,
                        source=str(baseline_csv),
                        scenario="mixed",
                        csv_path=baseline_csv,
                        events=events,
                        batch_size=batch_size,
                        warmup_events=warmup_events,
                    )
                )
                continue

            if not case_id.startswith("mock-"):
                csv_path = tmp_root / f"{case_id}.csv"
                _prepare_case_csv(case_id, csv_path, events)
                results.append(
                    _run_single_case(
                        case_id=case_id,
                        source="simulated-line",
                        scenario=case_id,
                        csv_path=csv_path,
                        events=events,
                        batch_size=batch_size,
                        warmup_events=warmup_events,
                    )
                )
                continue
            scenario = case_id.removeprefix("mock-")
            csv_path = tmp_root / f"{case_id}.csv"
            _mock_case_csv(csv_path, "pump", scenario, events)
            results.append(
                _run_single_case(
                    case_id=case_id,
                    source="mock-generator",
                    scenario=scenario,
                    csv_path=csv_path,
                    events=events,
                    batch_size=batch_size,
                    warmup_events=warmup_events,
                )
            )
    return RealWorldSimulatorResult(cases=tuple(results))


def format_result(result: RealWorldSimulatorResult) -> str:
    lines = [
        "case_id | source | scenario | events/sec | p99_ms | batches | invalid_events",
        "-" * 100,
    ]
    for case in result.cases:
        lines.append(
            f"{case.case_id} | {case.source} | {case.scenario} | {case.events_per_second} | {case.latency_p99_ms} | {case.batches} | {case.invalid_events}"
        )
    if result.cases:
        lines.append("-" * 100)
        lines.append(f"avg | - | - | {result.average_events_per_second} | {result.average_latency_p99_ms} | - | -")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark real-world simulator scenarios using local industrial data sources.")
    parser.add_argument("--csv", type=Path, default=Path("data/benchmarks/industrial_mixed_benchmark.csv"))
    parser.add_argument("--events", type=int, default=10_000)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument("--warmup-events", type=int, default=0)
    parser.add_argument(
        "--cases",
        default=None,
        help="Comma-separated case ids: mock-normal,mock-drift,mock-spike,multi-plc-line,burst-load,dropout-reconnect,industrial-benchmark",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    case_ids = [part.strip() for part in args.cases.split(",") if part.strip()] if args.cases else None
    result = run_suite(
        baseline_csv=args.csv,
        events=args.events,
        batch_size=args.batch_size,
        warmup_events=args.warmup_events,
        cases=case_ids,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

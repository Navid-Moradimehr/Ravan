from __future__ import annotations

import argparse
import tempfile
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Iterable

from services.benchmarks.mixed_replay import BenchmarkResult, format_result as format_replay_result, run_benchmark as run_mixed_replay_benchmark
from services.datasets.mock_generator import ALL_PRESETS, MockGeneratorConfig, generate_csv
from services.scenarios.engine import ScenarioState, ScenarioType


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
                raise ValueError(f"unknown simulator case: {case_id}")
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
    parser.add_argument("--cases", default=None, help="Comma-separated case ids: mock-normal,mock-drift,mock-spike,industrial-benchmark")
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

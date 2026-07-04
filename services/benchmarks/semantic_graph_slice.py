from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from services.assets.model import load_hierarchy
from services.common.semantic_core import SemanticGraph


@dataclass(frozen=True)
class SemanticGraphSliceBenchmarkResult:
    hierarchy_path: str
    iterations: int
    warmup_iterations: int
    entity_count: int
    relationship_count: int
    measurement_count: int
    elapsed_seconds: float
    graphs_per_second: float
    entities_per_second: float
    relationships_per_second: float


def run_benchmark(
    hierarchy_path: Path,
    *,
    iterations: int = 1_000,
    warmup_iterations: int = 100,
) -> SemanticGraphSliceBenchmarkResult:
    hierarchy = load_hierarchy(hierarchy_path)

    for _ in range(max(0, warmup_iterations)):
        SemanticGraph.from_asset_hierarchy(hierarchy, source_uri=str(hierarchy_path))

    started = time.perf_counter()
    last_graph: SemanticGraph | None = None
    for _ in range(max(1, iterations)):
        last_graph = SemanticGraph.from_asset_hierarchy(hierarchy, source_uri=str(hierarchy_path))
    elapsed = max(time.perf_counter() - started, 1e-9)
    if last_graph is None:
        last_graph = SemanticGraph.from_asset_hierarchy(hierarchy, source_uri=str(hierarchy_path))

    counts = last_graph.counts()
    graphs_per_second = iterations / elapsed
    entity_count = counts["entities"]
    relationship_count = counts["relationships"]
    measurement_count = counts["measurements"]
    entities_per_second = (entity_count * iterations) / elapsed
    relationships_per_second = (relationship_count * iterations) / elapsed

    return SemanticGraphSliceBenchmarkResult(
        hierarchy_path=str(hierarchy_path),
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        entity_count=entity_count,
        relationship_count=relationship_count,
        measurement_count=measurement_count,
        elapsed_seconds=elapsed,
        graphs_per_second=graphs_per_second,
        entities_per_second=entities_per_second,
        relationships_per_second=relationships_per_second,
    )


def format_result(result: SemanticGraphSliceBenchmarkResult) -> str:
    return "\n".join(
        [
            f"hierarchy_path={result.hierarchy_path}",
            f"iterations={result.iterations}",
            f"warmup_iterations={result.warmup_iterations}",
            f"entity_count={result.entity_count}",
            f"relationship_count={result.relationship_count}",
            f"measurement_count={result.measurement_count}",
            f"elapsed_seconds={result.elapsed_seconds}",
            f"graphs_per_second={result.graphs_per_second}",
            f"entities_per_second={result.entities_per_second}",
            f"relationships_per_second={result.relationships_per_second}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark semantic graph projection from the industrial asset hierarchy.")
    parser.add_argument("--hierarchy", type=Path, default=Path("config/assets.yaml"))
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--warmup-iterations", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(args.hierarchy, iterations=args.iterations, warmup_iterations=args.warmup_iterations)
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

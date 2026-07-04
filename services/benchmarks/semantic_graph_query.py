from __future__ import annotations

import argparse
import time
from dataclasses import dataclass
from pathlib import Path

from services.common.semantic_core import load_semantic_graph_from_assets


DEFAULT_QUERIES = (
    "Pump temperature relationship",
    "asset hierarchy site line cell",
    "pressure measurement for pump",
)


@dataclass(frozen=True)
class SemanticGraphQueryBenchmarkResult:
    hierarchy_path: str
    iterations: int
    warmup_iterations: int
    query_count: int
    matched_entities: int
    matched_relationships: int
    elapsed_seconds: float
    queries_per_second: float


def run_benchmark(
    hierarchy_path: Path,
    *,
    iterations: int = 1_000,
    warmup_iterations: int = 100,
    queries: tuple[str, ...] = DEFAULT_QUERIES,
    limit: int = 10,
) -> SemanticGraphQueryBenchmarkResult:
    graph = load_semantic_graph_from_assets(hierarchy_path)

    for _ in range(max(0, warmup_iterations)):
        for query in queries:
            graph.graph_search(query, limit=limit)

    started = time.perf_counter()
    matched_entities = 0
    matched_relationships = 0
    for _ in range(max(1, iterations)):
        for query in queries:
            result = graph.graph_search(query, limit=limit)
            matched_entities += len(result["entities"])
            matched_relationships += len(result["relationships"])
    elapsed = max(time.perf_counter() - started, 1e-9)
    total_queries = max(1, iterations) * len(queries)

    return SemanticGraphQueryBenchmarkResult(
        hierarchy_path=str(hierarchy_path),
        iterations=iterations,
        warmup_iterations=warmup_iterations,
        query_count=len(queries),
        matched_entities=matched_entities,
        matched_relationships=matched_relationships,
        elapsed_seconds=elapsed,
        queries_per_second=total_queries / elapsed,
    )


def format_result(result: SemanticGraphQueryBenchmarkResult) -> str:
    return "\n".join(
        [
            f"hierarchy_path={result.hierarchy_path}",
            f"iterations={result.iterations}",
            f"warmup_iterations={result.warmup_iterations}",
            f"query_count={result.query_count}",
            f"matched_entities={result.matched_entities}",
            f"matched_relationships={result.matched_relationships}",
            f"elapsed_seconds={result.elapsed_seconds}",
            f"queries_per_second={result.queries_per_second}",
        ]
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Benchmark semantic graph query throughput.")
    parser.add_argument("--hierarchy", type=Path, default=Path("config/assets.yaml"))
    parser.add_argument("--iterations", type=int, default=1_000)
    parser.add_argument("--warmup-iterations", type=int, default=100)
    parser.add_argument("--limit", type=int, default=10)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = run_benchmark(
        args.hierarchy,
        iterations=args.iterations,
        warmup_iterations=args.warmup_iterations,
        limit=args.limit,
    )
    print(format_result(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

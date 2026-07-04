from __future__ import annotations

from pathlib import Path

from services.benchmarks.semantic_graph_query import format_result, run_benchmark


def test_semantic_graph_query_benchmark_reports_throughput() -> None:
    result = run_benchmark(Path("config/assets.yaml"), iterations=100, warmup_iterations=10, limit=5)

    assert result.iterations == 100
    assert result.query_count == 3
    assert result.queries_per_second > 0
    assert result.matched_entities > 0
    assert result.matched_relationships > 0
    assert "queries_per_second" in format_result(result)

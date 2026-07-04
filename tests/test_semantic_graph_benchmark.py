from __future__ import annotations

from pathlib import Path

from services.benchmarks.semantic_graph_slice import format_result, run_benchmark


def test_semantic_graph_projection_benchmark_reports_throughput() -> None:
    result = run_benchmark(Path("config/assets.yaml"), iterations=100, warmup_iterations=10)

    assert result.iterations == 100
    assert result.entity_count > 0
    assert result.relationship_count > 0
    assert result.measurement_count == 9
    assert result.graphs_per_second > 0
    assert result.entities_per_second > 0
    assert "graphs_per_second" in format_result(result)

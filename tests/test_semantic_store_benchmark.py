from __future__ import annotations

from pathlib import Path

from services.benchmarks.semantic_store_write import format_result, run_benchmark


def test_semantic_store_write_benchmark_reports_throughput(tmp_path: Path) -> None:
    result = run_benchmark(tmp_path / "semantic-store.json", iterations=50, warmup_iterations=5)

    assert result.iterations == 50
    assert result.writes_per_second > 0
    assert result.entity_count > 0
    assert result.relationship_count > 0
    assert result.lineage_count > 0
    assert "writes_per_second" in format_result(result)

from services.benchmarks.training_dataset import run_benchmark


def test_training_dataset_benchmark_reports_throughput() -> None:
    result = run_benchmark(iterations=1, records_per_iteration=20)
    assert result.records_per_second > 0

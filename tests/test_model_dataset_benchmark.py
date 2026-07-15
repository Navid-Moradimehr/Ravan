from services.benchmarks.model_dataset import run_benchmark


def test_model_dataset_benchmark_reports_throughput():
    result = run_benchmark(records=100)
    assert result.records_per_second > 0
    assert result.steps > 0

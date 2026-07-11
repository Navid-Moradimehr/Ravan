from services.benchmarks.multi_site_failure import run_benchmark


def test_multi_site_failure_recovers_without_duplicates():
    result = run_benchmark(sites=3, events_per_site=100, outage_events_per_site=25)
    assert result.local_events_written == 300
    assert result.queued_during_outage == 75
    assert result.central_events_written == 300
    assert result.duplicate_events == 0
    assert result.recovery_complete

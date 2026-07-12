from services.benchmarks.multi_site_simulator import SiteSimulation, run_simulation


def test_multi_site_simulation_isolates_and_recovers_each_site(tmp_path):
    report = run_simulation(
        site_definitions=(SiteSimulation("north"), SiteSimulation("south")),
        events_per_site=120,
        outage_events_per_site=30,
        spool_root=tmp_path / "spools",
    )

    assert report.passed, report
    assert report.central_events_written == 240
    assert report.central_unique_event_ids == 240
    assert report.recovery_complete
    assert report.cross_site_events == 0
    assert all(item.replayed == 30 for item in report.site_results)
    assert all(item.site_isolation_errors == 0 for item in report.site_results)


def test_multi_site_simulation_rejects_invalid_size():
    try:
        run_simulation(events_per_site=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid event count to fail")

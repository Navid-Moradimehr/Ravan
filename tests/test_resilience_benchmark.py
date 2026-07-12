from services.benchmarks.resilience import run_campaign


def test_resilience_campaign_replays_outage_queue_without_loss(tmp_path):
    report = run_campaign(events=250, outage_events=75, spool_dir=tmp_path / "spool")

    assert report.passed
    assert report.rejected_events > 0
    assert 0 < report.queued_events <= 75
    assert report.replayed_events == report.queued_events
    assert report.pending_after_recovery == 0
    assert report.unaccounted_events == 0


def test_resilience_campaign_rejects_invalid_event_count():
    try:
        run_campaign(events=0)
    except ValueError as exc:
        assert "positive" in str(exc)
    else:
        raise AssertionError("expected invalid event count to fail")

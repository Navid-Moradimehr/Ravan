from __future__ import annotations

from services.ingestion.mock_generator import GeneratorStats, build_event
from services.scenarios.engine import ScenarioState, ScenarioType


def test_build_event_honors_explicit_site_id() -> None:
    scenario = ScenarioState(ScenarioType.NORMAL)
    event = build_event(4, scenario, site_id="site-03")

    assert event.site_id == "site-03"
    assert event.device_id.startswith("device-")


def test_generator_stats_accounts_delivery_outcomes() -> None:
    stats = GeneratorStats()
    stats.attempted = 3
    stats.delivery_callback(None, None)
    stats.delivery_callback(RuntimeError("broker"), None)
    stats.finished_at = stats.started_at + 1

    report = stats.report(site_id="site-01", topic="industrial.normalized", target_rate=3)

    assert report["acknowledged"] == 1
    assert report["failed"] == 1
    assert report["effective_attempt_rate"] == 3.0


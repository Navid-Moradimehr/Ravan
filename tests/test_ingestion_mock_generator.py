from __future__ import annotations

from services.ingestion.mock_generator import build_event
from services.scenarios.engine import ScenarioState, ScenarioType


def test_build_event_honors_explicit_site_id() -> None:
    scenario = ScenarioState(ScenarioType.NORMAL)
    event = build_event(4, scenario, site_id="site-03")

    assert event.site_id == "site-03"
    assert event.device_id.startswith("device-")

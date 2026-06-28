"""Tests for the mock industrial data generator."""
from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from services.datasets.mock_generator import (
    AssetConfig,
    MockGeneratorConfig,
    PUMP_ASSETS,
    MOTOR_ASSETS,
    TURBINE_ASSETS,
    ALL_PRESETS,
    generate_value,
    generate_event,
    generate_csv,
)
from services.scenarios.engine import ScenarioState, ScenarioType


class TestMockGenerator:
    def test_generate_value_normal(self):
        asset = AssetConfig("Pump-01", "Temperature", "c", 55.0, 5.0, 0.0, 120.0)
        scenario = ScenarioState(ScenarioType.NORMAL)
        value = generate_value(asset, scenario)
        assert 0.0 <= value <= 120.0

    def test_generate_value_spike(self):
        asset = AssetConfig("Pump-01", "Temperature", "c", 55.0, 5.0, 0.0, 120.0)
        scenario = ScenarioState(ScenarioType.SPIKE, params={"spike_magnitude": 50.0})
        values = [generate_value(asset, scenario) for _ in range(100)]
        # At least some values should be spiked
        assert any(v > 70.0 or v < 40.0 for v in values)

    def test_generate_event_structure(self):
        asset = AssetConfig("Pump-01", "Temperature", "c", 55.0, 5.0, 0.0, 120.0)
        scenario = ScenarioState(ScenarioType.NORMAL)
        event = generate_event(asset, scenario)
        assert event["asset_id"] == "Pump-01"
        assert event["tag"] == "Temperature"
        assert event["unit"] == "c"
        assert "value" in event
        assert "quality" in event
        assert "fault_type" in event
        assert "scenario_id" in event

    def test_generate_csv(self):
        config = MockGeneratorConfig(
            assets=PUMP_ASSETS[:2],
            scenario=ScenarioState(ScenarioType.NORMAL),
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            path = Path(f.name)
        try:
            generate_csv(config, path, num_rows=10)
            assert path.exists()
            content = path.read_text()
            assert "asset_id" in content
            assert "Pump-01" in content
            assert "Temperature" in content
        finally:
            path.unlink()

    def test_presets(self):
        assert len(PUMP_ASSETS) == 9
        assert len(MOTOR_ASSETS) == 8
        assert len(TURBINE_ASSETS) == 5
        assert len(ALL_PRESETS["all"]) == 22

    def test_scenario_labels(self):
        scenario = ScenarioState(ScenarioType.DEGRADATION, scenario_id="sc-123")
        event = generate_event(PUMP_ASSETS[0], scenario)
        assert event["fault_type"] == "degradation"
        assert event["scenario_id"] == "sc-123"
        assert event["ground_truth_severity"] == "critical"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

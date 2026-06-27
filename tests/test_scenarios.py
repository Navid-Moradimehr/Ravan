from __future__ import annotations

import math

import pytest

from services.scenarios.engine import (
    ScenarioState,
    ScenarioType,
    advance_scenario,
    apply_scenario,
    load_scenario_from_env,
)


def test_load_normal_scenario_by_default() -> None:
    state = load_scenario_from_env()
    assert state.scenario_type == ScenarioType.NORMAL
    assert state.scenario_id.startswith("sc-")


def test_normal_mutator_unchanged() -> None:
    state = ScenarioState(scenario_type=ScenarioType.NORMAL, step=0)
    assert apply_scenario(50.0, state) == 50.0


def test_drift_mutator_increases_over_time() -> None:
    state = ScenarioState(scenario_type=ScenarioType.DRIFT, step=10, params={"drift_rate": 0.5})
    result = apply_scenario(50.0, state)
    assert result == 55.0


def test_spike_mutator_can_add_large_deviation() -> None:
    state = ScenarioState(scenario_type=ScenarioType.SPIKE, step=0, params={"spike_prob": 1.0, "spike_magnitude": 30.0})
    result = apply_scenario(50.0, state)
    assert abs(result - 50.0) == 30.0


def test_stuck_mutator_freezes_after_threshold() -> None:
    state = ScenarioState(scenario_type=ScenarioType.STUCK, step=100, params={"stuck_after": 50, "stuck_value": 42.0})
    result = apply_scenario(50.0, state)
    assert result == 42.0


def test_dropout_mutator_returns_nan() -> None:
    state = ScenarioState(scenario_type=ScenarioType.DROPOUT, step=0, params={"dropout_prob": 1.0})
    result = apply_scenario(50.0, state)
    assert math.isnan(result)


def test_noisy_mutator_adds_variance() -> None:
    state = ScenarioState(scenario_type=ScenarioType.NOISY, step=0, params={"noise_sigma": 0.0})
    result = apply_scenario(50.0, state)
    assert result == 50.0


def test_degradation_mutator_shifts_up() -> None:
    state = ScenarioState(scenario_type=ScenarioType.DEGRADATION, step=10, params={"degrade_rate": 1.0, "max_shift": 100.0})
    result = apply_scenario(50.0, state)
    assert result == 60.0


def test_ground_truth_severity_mapping() -> None:
    assert ScenarioState(scenario_type=ScenarioType.NORMAL).ground_truth_severity() == "normal"
    assert ScenarioState(scenario_type=ScenarioType.DRIFT).ground_truth_severity() == "warning"
    assert ScenarioState(scenario_type=ScenarioType.SPIKE).ground_truth_severity() == "critical"
    assert ScenarioState(scenario_type=ScenarioType.DEGRADATION).ground_truth_severity() == "critical"


def test_label_contains_expected_keys() -> None:
    state = ScenarioState(scenario_type=ScenarioType.DRIFT, scenario_id="sc-001", step=5)
    label = state.label()
    assert label["fault_type"] == "drift"
    assert label["scenario_id"] == "sc-001"
    assert label["ground_truth_severity"] == "warning"
    assert label["step"] == 5


def test_advance_scenario_increments_step() -> None:
    state = ScenarioState(step=3)
    advance_scenario(state)
    assert state.step == 4

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable


class ScenarioType(str, Enum):
    NORMAL = "normal"
    DRIFT = "drift"
    SPIKE = "spike"
    STUCK = "stuck"
    DROPOUT = "dropout"
    NOISY = "noisy"
    DEGRADATION = "degradation"
    MAINTENANCE_RESET = "maintenance_reset"


@dataclass
class ScenarioState:
    scenario_type: ScenarioType = ScenarioType.NORMAL
    scenario_id: str = "sc-000"
    step: int = 0
    active: bool = True
    params: dict[str, Any] = field(default_factory=dict)

    def label(self) -> dict[str, Any]:
        return {
            "fault_type": self.scenario_type.value,
            "scenario_id": self.scenario_id,
            "ground_truth_severity": self.ground_truth_severity(),
            "step": self.step,
        }

    def ground_truth_severity(self) -> str:
        mapping = {
            ScenarioType.NORMAL: "normal",
            ScenarioType.DRIFT: "warning",
            ScenarioType.SPIKE: "critical",
            ScenarioType.STUCK: "warning",
            ScenarioType.DROPOUT: "warning",
            ScenarioType.NOISY: "warning",
            ScenarioType.DEGRADATION: "critical",
            ScenarioType.MAINTENANCE_RESET: "normal",
        }
        return mapping.get(self.scenario_type, "normal")


def _env_scenario() -> str:
    return os.getenv("SCENARIO_TYPE", "normal").lower().strip()


def _env_scenario_id() -> str:
    return os.getenv("SCENARIO_ID", f"sc-{random.randint(100, 999):03d}")


def _env_params() -> dict[str, Any]:
    raw = os.getenv("SCENARIO_PARAMS", "")
    if not raw:
        return {}
    params: dict[str, Any] = {}
    for pair in raw.split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            try:
                params[k.strip()] = float(v.strip())
            except ValueError:
                params[k.strip()] = v.strip()
    return params


def load_scenario_from_env() -> ScenarioState:
    scenario_type = ScenarioType(_env_scenario())
    return ScenarioState(
        scenario_type=scenario_type,
        scenario_id=_env_scenario_id(),
        params=_env_params(),
    )


# Scenario mutators: each takes (base_value, step, params) and returns mutated value

ScenarioMutator = Callable[[float, int, dict[str, Any]], float]


def _normal_mutator(value: float, _step: int, _params: dict[str, Any]) -> float:
    return value


def _drift_mutator(value: float, step: int, params: dict[str, Any]) -> float:
    drift_rate = params.get("drift_rate", 0.02)
    return value + step * drift_rate


def _spike_mutator(value: float, step: int, params: dict[str, Any]) -> float:
    spike_prob = params.get("spike_prob", 0.05)
    spike_mag = params.get("spike_magnitude", 20.0)
    if random.random() < spike_prob:
        return value + random.choice([-1, 1]) * spike_mag
    return value


def _stuck_mutator(value: float, step: int, params: dict[str, Any]) -> float:
    stuck_after = int(params.get("stuck_after", 50))
    stuck_value = params.get("stuck_value", None)
    if step >= stuck_after:
        if stuck_value is not None:
            return float(stuck_value)
        return value  # freeze at last value
    return value


def _dropout_mutator(value: float, _step: int, params: dict[str, Any]) -> float:
    dropout_prob = params.get("dropout_prob", 0.03)
    if random.random() < dropout_prob:
        return float("nan")
    return value


def _noisy_mutator(value: float, _step: int, params: dict[str, Any]) -> float:
    noise_sigma = params.get("noise_sigma", 5.0)
    return value + random.gauss(0, noise_sigma)


def _degradation_mutator(value: float, step: int, params: dict[str, Any]) -> float:
    degrade_rate = params.get("degrade_rate", 0.05)
    max_shift = params.get("max_shift", 15.0)
    shift = min(step * degrade_rate, max_shift)
    return value + shift


def _maintenance_reset_mutator(value: float, _step: int, _params: dict[str, Any]) -> float:
    return value


_MUTATORS: dict[ScenarioType, ScenarioMutator] = {
    ScenarioType.NORMAL: _normal_mutator,
    ScenarioType.DRIFT: _drift_mutator,
    ScenarioType.SPIKE: _spike_mutator,
    ScenarioType.STUCK: _stuck_mutator,
    ScenarioType.DROPOUT: _dropout_mutator,
    ScenarioType.NOISY: _noisy_mutator,
    ScenarioType.DEGRADATION: _degradation_mutator,
    ScenarioType.MAINTENANCE_RESET: _maintenance_reset_mutator,
}


def apply_scenario(value: float, state: ScenarioState) -> float:
    mutator = _MUTATORS.get(state.scenario_type, _normal_mutator)
    return mutator(value, state.step, state.params)


def advance_scenario(state: ScenarioState) -> None:
    state.step += 1

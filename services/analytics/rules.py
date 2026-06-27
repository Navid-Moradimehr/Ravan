from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class Rule:
    name: str
    tag: str
    condition: str
    threshold: float
    severity: str

    def evaluate(self, event: dict[str, Any]) -> bool:
        value = float(event.get(self.tag, 0))
        if self.condition == ">=":
            return value >= self.threshold
        if self.condition == "<=":
            return value <= self.threshold
        if self.condition == ">":
            return value > self.threshold
        if self.condition == "<":
            return value < self.threshold
        return False


def default_rules() -> list[Rule]:
    return [
        Rule("high_temp", "temperature_c", ">=", 65.0, "warning"),
        Rule("crit_temp", "temperature_c", ">=", 80.0, "critical"),
        Rule("high_vib", "vibration_mm_s", ">=", 7.0, "warning"),
        Rule("crit_vib", "vibration_mm_s", ">=", 12.0, "critical"),
        Rule("high_press", "pressure_bar", ">=", 8.0, "warning"),
        Rule("crit_press", "pressure_bar", ">=", 12.0, "critical"),
    ]


def evaluate_rules(event: dict[str, Any], rules: list[Rule] | None = None) -> list[Rule]:
    if rules is None:
        rules = default_rules()
    return [r for r in rules if r.evaluate(event)]

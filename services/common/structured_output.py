from __future__ import annotations

import json
from typing import Any


INDUSTRIAL_SUMMARY_REQUIRED_KEYS = (
    "summary",
    "critical_devices",
    "warning_devices",
    "probable_causes",
    "recommended_actions",
    "batch_size",
    "severity_counts",
)


def parse_json_output(text: str) -> dict[str, Any] | None:
    candidate = text.strip()
    if not candidate:
        return None

    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if len(lines) >= 3:
            candidate = "\n".join(lines[1:-1]).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None

    return payload if isinstance(payload, dict) else None


def validate_industrial_summary(content: str | dict[str, Any]) -> tuple[bool, list[str], dict[str, Any] | None]:
    payload = content if isinstance(content, dict) else parse_json_output(content)
    if payload is None:
        return False, ["summary output is not valid JSON"], None

    errors: list[str] = []
    for key in INDUSTRIAL_SUMMARY_REQUIRED_KEYS:
        if key not in payload:
            errors.append(f"missing key: {key}")

    if "critical_devices" in payload and not isinstance(payload["critical_devices"], list):
        errors.append("critical_devices must be a list")
    if "warning_devices" in payload and not isinstance(payload["warning_devices"], list):
        errors.append("warning_devices must be a list")
    if "probable_causes" in payload and not isinstance(payload["probable_causes"], list):
        errors.append("probable_causes must be a list")
    if "recommended_actions" in payload and not isinstance(payload["recommended_actions"], list):
        errors.append("recommended_actions must be a list")
    if "severity_counts" in payload and not isinstance(payload["severity_counts"], dict):
        errors.append("severity_counts must be a mapping")

    return len(errors) == 0, errors, payload


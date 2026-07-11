"""Operator-configurable controls for raw payload archival."""

from __future__ import annotations

import copy
import json
from typing import Any


def sanitize_raw_event(event: dict[str, Any], *, max_bytes: int = 1_048_576, redact_fields: tuple[str, ...] = ()) -> tuple[dict[str, Any] | None, str | None]:
    candidate = copy.deepcopy(event)
    for field in redact_fields:
        if field in candidate:
            candidate[field] = "[REDACTED]"
    candidate["event_stage"] = "raw"
    candidate["payload_json"] = json.dumps(candidate, sort_keys=True, default=str)
    encoded_size = len(json.dumps(candidate, sort_keys=True, default=str).encode("utf-8"))
    if encoded_size > max_bytes:
        return None, f"raw payload exceeds max bytes ({encoded_size}>{max_bytes})"
    return candidate, None

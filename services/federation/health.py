"""Read-only federation health state shared by transport adapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


def federation_health(path: str | Path | None = None) -> dict[str, Any]:
    location = Path(path or os.getenv("FEDERATION_STATUS_PATH", ".datastream/federation-status.json"))
    if not location.exists():
        return {
            "status": "unknown",
            "source": str(location),
            "reason": "no transport adapter has published a status snapshot",
        }
    try:
        payload = json.loads(location.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {"status": "invalid", "source": str(location)}
    except (OSError, json.JSONDecodeError) as exc:
        return {"status": "invalid", "source": str(location), "reason": str(exc)}

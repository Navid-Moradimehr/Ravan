from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time
from typing import Any


@dataclass
class ServiceHealthState:
    name: str
    running: bool = False
    degraded: bool = False
    last_error: str | None = None
    degraded_reason: str | None = None
    last_ok_epoch: float | None = None
    last_error_epoch: float | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def mark_running(self) -> None:
        self.running = True
        self.last_ok_epoch = time()

    def mark_stopped(self) -> None:
        self.running = False

    def mark_ok(self) -> None:
        self.degraded = False
        self.last_error = None
        self.degraded_reason = None
        self.last_ok_epoch = time()

    def mark_degraded(self, reason: str, error: str | None = None) -> None:
        self.degraded = True
        self.degraded_reason = reason
        self.last_error = error or reason
        self.last_error_epoch = time()

    def snapshot(self) -> dict[str, Any]:
        return asdict(self)

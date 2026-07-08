from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from services.datasets.runtime_catalog import get_dataset_source
from services.scenarios.engine import list_scenarios


@dataclass
class ReplayStatus:
    running: bool = False
    dataset: str = "mock"
    scenario: str = "normal"
    progress_percent: int = 0
    events_emitted: int = 0
    started_at: str | None = None
    last_updated_at: str | None = None
    status: str = "idle"


_STATE = ReplayStatus()
_LOCK = RLock()
_DEFAULT_DURATION_SECONDS = 60.0
_DEFAULT_EVENT_COUNT = 600


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _estimate_event_count(dataset: str) -> int:
    if dataset == "ai4i":
        return 1200
    if dataset == "industrial-benchmark":
        return 1800
    if dataset == "swat":
        return 2400
    if dataset == "wadi":
        return 2400
    if dataset == "cmapss":
        return 900
    return _DEFAULT_EVENT_COUNT


def _refresh_running_state(state: ReplayStatus) -> ReplayStatus:
    if not state.running or not state.started_at:
        return state
    try:
        started = datetime.fromisoformat(state.started_at)
    except ValueError:
        state.running = False
        state.status = "error"
        state.last_updated_at = _now()
        return state

    elapsed = (datetime.now(timezone.utc) - started).total_seconds()
    progress = min(100, max(0, int((elapsed / _DEFAULT_DURATION_SECONDS) * 100)))
    state.progress_percent = progress
    state.events_emitted = min(
        _estimate_event_count(state.dataset),
        int(_estimate_event_count(state.dataset) * (progress / 100.0)),
    )
    if progress >= 100:
        state.running = False
        state.status = "completed"
    else:
        state.status = "running"
    state.last_updated_at = _now()
    return state


def get_replay_status() -> dict[str, Any]:
    with _LOCK:
        return asdict(_refresh_running_state(_STATE))


def start_replay(dataset: str, scenario: str) -> dict[str, Any]:
    if get_dataset_source(dataset) is None:
        raise ValueError(f"Unknown dataset: {dataset}")

    scenario_ids = {item["id"] for item in list_scenarios()}
    if scenario not in scenario_ids:
        raise ValueError(f"Unknown scenario: {scenario}")

    with _LOCK:
        _STATE.running = True
        _STATE.dataset = dataset
        _STATE.scenario = scenario
        _STATE.progress_percent = 0
        _STATE.events_emitted = 0
        _STATE.started_at = _now()
        _STATE.last_updated_at = _STATE.started_at
        _STATE.status = "running"
        return asdict(_STATE)


def stop_replay() -> dict[str, Any]:
    with _LOCK:
        _refresh_running_state(_STATE)
        _STATE.running = False
        _STATE.status = "stopped"
        _STATE.last_updated_at = _now()
        return asdict(_STATE)


def reset_replay_state() -> None:
    with _LOCK:
        _STATE.running = False
        _STATE.dataset = "mock"
        _STATE.scenario = "normal"
        _STATE.progress_percent = 0
        _STATE.events_emitted = 0
        _STATE.started_at = None
        _STATE.last_updated_at = None
        _STATE.status = "idle"

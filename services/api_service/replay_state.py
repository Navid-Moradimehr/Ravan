from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import csv
import json
import os
import threading
import time
from pathlib import Path
from threading import Event, RLock
from typing import Any

from services.common.brokers import resolve_kafka_brokers
from services.common.stream_scope import stream_partition_key
from services.datasets.replayer import map_row_to_event, read_csv_rows
from services.edge_ingest.model import to_json_bytes
from services.datasets.runtime_catalog import get_dataset_source
from services.scenarios.engine import list_scenarios


@dataclass
class ReplayStatus:
    running: bool = False
    dataset: str = ""
    scenario: str = "normal"
    progress_percent: int = 0
    events_emitted: int = 0
    started_at: str | None = None
    last_updated_at: str | None = None
    status: str = "idle"
    error: str | None = None


_STATE = ReplayStatus()
_LOCK = RLock()
_DEFAULT_DURATION_SECONDS = 60.0
_DEFAULT_EVENT_COUNT = 600
_STOP_EVENT = Event()
_THREAD: threading.Thread | None = None


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
    if state.running:
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

    source_path = _configured_dataset_path(dataset)
    if source_path is None:
        raise ValueError(
            f"No replay source configured for {dataset}; set DATASET_REPLAY_PATHS to a JSON mapping of dataset IDs to CSV files"
        )

    with _LOCK:
        if _STATE.running:
            raise ValueError("A replay is already running")
        _STOP_EVENT.clear()
        _STATE.running = True
        _STATE.dataset = dataset
        _STATE.scenario = scenario
        _STATE.progress_percent = 0
        _STATE.events_emitted = 0
        _STATE.started_at = _now()
        _STATE.last_updated_at = _STATE.started_at
        _STATE.status = "running"
        _STATE.error = None
        global _THREAD
        _THREAD = threading.Thread(
            target=_run_replay,
            args=(dataset, scenario, source_path),
            name="datastream-replay",
            daemon=True,
        )
        _THREAD.start()
        return asdict(_STATE)


def stop_replay() -> dict[str, Any]:
    with _LOCK:
        _STOP_EVENT.set()
        _STATE.running = False
        _STATE.status = "stopped"
        _STATE.last_updated_at = _now()
        return asdict(_STATE)


def reset_replay_state() -> None:
    with _LOCK:
        _STOP_EVENT.set()
        _STATE.running = False
        _STATE.dataset = ""
        _STATE.scenario = "normal"
        _STATE.progress_percent = 0
        _STATE.events_emitted = 0
        _STATE.started_at = None
        _STATE.last_updated_at = None
        _STATE.status = "idle"
        _STATE.error = None


def _configured_dataset_path(dataset: str) -> Path | None:
    raw = os.getenv("DATASET_REPLAY_PATHS", "").strip()
    if not raw:
        return None
    try:
        paths = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("DATASET_REPLAY_PATHS must be valid JSON") from exc
    path = paths.get(dataset) if isinstance(paths, dict) else None
    if not path:
        return None
    resolved = Path(str(path)).expanduser()
    if not resolved.is_file():
        raise ValueError(f"Configured replay source does not exist: {resolved}")
    return resolved


def _set_progress(emitted: int, target: int) -> None:
    with _LOCK:
        _STATE.events_emitted = emitted
        _STATE.progress_percent = min(100, int(emitted * 100 / max(target, 1)))
        _STATE.last_updated_at = _now()


def _finish(status: str, error: str | None = None) -> None:
    with _LOCK:
        _STATE.running = False
        _STATE.status = status
        _STATE.error = error
        _STATE.progress_percent = 100 if status == "completed" else _STATE.progress_percent
        _STATE.last_updated_at = _now()


def _run_replay(dataset: str, scenario: str, source_path: Path | None) -> None:
    """Produce replay records and update state from acknowledged publication."""
    try:
        from confluent_kafka import Producer

        producer = Producer({
            "bootstrap.servers": resolve_kafka_brokers("localhost:19092"),
            "client.id": "historian-replay",
            "enable.idempotence": True,
            "acks": "all",
        })
        topic = os.getenv("REPLAY_TOPIC", "industrial.normalized")
        rate = max(1, int(os.getenv("REPLAY_RATE_PER_SECOND", "100")))
        if source_path is None:
            raise ValueError("Replay requires an operator-provided CSV source")
        target = _estimate_csv_count(source_path)
        emitted = 0
        rows = iter(read_csv_rows(source_path))
        mapping = {"asset_id": "asset_id", "tag": "tag", "value": "value", "source_protocol": "source_protocol", "source_id": "source_id", "quality": "quality", "unit": "unit", "site": "site", "line": "line", "ts_source": "ts_source"}
        while not _STOP_EVENT.is_set() and emitted < target:
            try:
                row = next(rows)
            except StopIteration:
                break
            event = map_row_to_event(row, mapping)
            _publish_replay_event(producer, topic, event)
            emitted += 1
            _set_progress(emitted, target)
            time.sleep(1 / rate)
        remaining = producer.flush(10)
        if remaining:
            raise RuntimeError(f"{remaining} replay record(s) were not acknowledged by Kafka")
        _finish("stopped" if _STOP_EVENT.is_set() else "completed")
    except Exception as exc:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("replay worker failed")
        _finish("error", str(exc))


def _publish_replay_event(producer: Any, topic: str, event: dict[str, Any]) -> None:
    producer.produce(topic, key=stream_partition_key(event), value=to_json_bytes(event))
    producer.poll(0)


def _estimate_csv_count(path: Path) -> int:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.DictReader(handle)))

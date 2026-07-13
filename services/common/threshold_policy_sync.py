from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from services.common.brokers import resolve_kafka_brokers

logger = logging.getLogger(__name__)

POLICY_TOPIC = os.getenv("THRESHOLD_POLICY_TOPIC", "platform.metadata.threshold-policies")
OUTBOX_TABLE = "metadata_threshold_policy_outbox"
DEFAULT_GROUP_PREFIX = "threshold-policy-sync"

_CACHE_LOCK = threading.Lock()
_POLICY_CACHE: dict[tuple[str, str, str], dict[str, Any]] = {}
_POLICY_VERSIONS: dict[tuple[str, str, str], int] = {}
_SYNC_STATE: dict[str, Any] = {
    "topic": POLICY_TOPIC,
    "status": "bootstrap",
    "version": 0,
    "published": 0,
    "consumed": 0,
    "pending_outbox": 0,
    "last_error": "",
    "last_published_at": None,
    "last_consumed_at": None,
}


@dataclass(slots=True, frozen=True)
class ThresholdPolicyEnvelope:
    policy_key: str
    site_id: str
    asset_id: str
    tag: str
    version: int
    sync_status: str
    published_at: str
    policy: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "threshold_policy",
            "policy_key": self.policy_key,
            "site_id": self.site_id,
            "asset_id": self.asset_id,
            "tag": self.tag,
            "version": self.version,
            "sync_status": self.sync_status,
            "published_at": self.published_at,
            "policy": self.policy,
        }


def policy_key(site_id: str, asset_id: str, tag: str) -> str:
    return "|".join([str(site_id), str(asset_id), str(tag)])


def ensure_outbox_table() -> None:
    from services.historian.client import get_connection

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {OUTBOX_TABLE} (
                    outbox_id BIGSERIAL PRIMARY KEY,
                    policy_key TEXT NOT NULL,
                    site_id TEXT NOT NULL,
                    asset_id TEXT NOT NULL,
                    tag TEXT NOT NULL,
                    policy_version INTEGER NOT NULL,
                    payload JSONB NOT NULL,
                    sync_status TEXT NOT NULL DEFAULT 'pending',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    published_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {OUTBOX_TABLE}_status_idx
                ON {OUTBOX_TABLE} (sync_status, outbox_id)
                """
            )
            cur.execute(
                f"""
                CREATE INDEX IF NOT EXISTS {OUTBOX_TABLE}_policy_idx
                ON {OUTBOX_TABLE} (policy_key, policy_version)
                """
            )
        conn.commit()


def cache_policy(policy: dict[str, Any]) -> dict[str, Any]:
    key = (str(policy.get("site_id", "")), str(policy.get("asset_id", "")), str(policy.get("tag", "")))
    version = int(policy.get("version", 0) or 0)
    with _CACHE_LOCK:
        _POLICY_CACHE[key] = dict(policy)
        _POLICY_VERSIONS[key] = version
        _SYNC_STATE["version"] = max(int(_SYNC_STATE.get("version", 0) or 0), version)
    return _POLICY_CACHE[key]


def cache_policies(policies: list[dict[str, Any]]) -> None:
    for policy in policies:
        cache_policy(policy)
    with _CACHE_LOCK:
        _SYNC_STATE["status"] = "synced"
        _SYNC_STATE["last_consumed_at"] = datetime.now(timezone.utc).isoformat()


def clear_cache() -> None:
    with _CACHE_LOCK:
        _POLICY_CACHE.clear()
        _POLICY_VERSIONS.clear()


def get_cached_policy(site_id: str, asset_id: str, tag: str) -> dict[str, Any] | None:
    with _CACHE_LOCK:
        return _POLICY_CACHE.get((site_id, asset_id, tag))


def get_cached_version(site_id: str, asset_id: str, tag: str) -> int:
    with _CACHE_LOCK:
        return int(_POLICY_VERSIONS.get((site_id, asset_id, tag), 0) or 0)


def list_cached_policies() -> list[dict[str, Any]]:
    with _CACHE_LOCK:
        return [dict(policy) for policy in _POLICY_CACHE.values()]


def apply_threshold_snapshot(policies: list[dict[str, Any]], *, source: str, status: str = "synced") -> None:
    clear_cache()
    cache_policies([dict(policy) for policy in policies])
    with _CACHE_LOCK:
        _SYNC_STATE["status"] = status
        _SYNC_STATE["source"] = source
        _SYNC_STATE["last_error"] = ""
        _SYNC_STATE["last_consumed_at"] = datetime.now(timezone.utc).isoformat()


def threshold_policy_sync_state() -> dict[str, Any]:
    with _CACHE_LOCK:
        explicit_count = len(_POLICY_CACHE)
        return {
            **_SYNC_STATE,
            "policy_count": explicit_count,
        }


def set_sync_error(error: str, *, status: str = "degraded") -> None:
    with _CACHE_LOCK:
        _SYNC_STATE["status"] = status
        _SYNC_STATE["last_error"] = error


def build_policy_envelope(policy: dict[str, Any], *, sync_status: str = "pending") -> ThresholdPolicyEnvelope:
    version = int(policy.get("version", 0) or 0)
    site_id = str(policy.get("site_id", ""))
    asset_id = str(policy.get("asset_id", ""))
    tag = str(policy.get("tag", ""))
    payload = dict(policy)
    payload["policy_key"] = policy_key(site_id, asset_id, tag)
    payload["sync_status"] = sync_status
    payload["published_at"] = datetime.now(timezone.utc).isoformat()
    payload["event_id"] = str(uuid.uuid4())
    return ThresholdPolicyEnvelope(
        policy_key=payload["policy_key"],
        site_id=site_id,
        asset_id=asset_id,
        tag=tag,
        version=version,
        sync_status=sync_status,
        published_at=payload["published_at"],
        policy=payload,
    )


def enqueue_policy_outbox(policy: dict[str, Any], *, sync_status: str = "pending") -> dict[str, Any]:
    ensure_outbox_table()
    envelope = build_policy_envelope(policy, sync_status=sync_status)
    from services.historian.client import get_connection

    row = {
        "policy_key": envelope.policy_key,
        "site_id": envelope.site_id,
        "asset_id": envelope.asset_id,
        "tag": envelope.tag,
        "policy_version": envelope.version,
        "payload": envelope.to_dict(),
        "sync_status": sync_status,
    }
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                INSERT INTO {OUTBOX_TABLE} (
                    policy_key, site_id, asset_id, tag, policy_version, payload, sync_status, attempts, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 0, now())
                """,
                (
                    row["policy_key"],
                    row["site_id"],
                    row["asset_id"],
                    row["tag"],
                    row["policy_version"],
                    json.dumps(row["payload"]),
                    sync_status,
                ),
            )
        conn.commit()
    with _CACHE_LOCK:
        _SYNC_STATE["pending_outbox"] = int(_SYNC_STATE.get("pending_outbox", 0) or 0) + 1
    return row


def _producer():
    from confluent_kafka import Producer

    brokers = resolve_kafka_brokers("localhost:19092")
    return Producer(
        {
            "bootstrap.servers": brokers,
            "client.id": "threshold-policy-sync",
            "enable.idempotence": True,
            "acks": "all",
            "linger.ms": 10,
            "compression.type": "lz4",
        }
    )


def _consumer(group_id: str):
    from confluent_kafka import Consumer

    brokers = resolve_kafka_brokers("localhost:19092")
    consumer = Consumer(
        {
            "bootstrap.servers": brokers,
            "group.id": group_id,
            "auto.offset.reset": os.getenv("THRESHOLD_POLICY_AUTO_OFFSET_RESET", "latest"),
            "enable.auto.commit": True,
            "enable.auto.offset.store": True,
        }
    )
    consumer.subscribe([POLICY_TOPIC])
    return consumer


def _publish_payload(producer: Any, payload: dict[str, Any]) -> None:
    key = policy_key(payload["site_id"], payload["asset_id"], payload["tag"]).encode("utf-8")
    producer.produce(POLICY_TOPIC, key=key, value=json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    if producer.flush(10):
        raise RuntimeError(f"threshold policy delivery timed out for {key.decode('utf-8')}")


def drain_policy_outbox(*, batch_size: int = 100) -> int:
    ensure_outbox_table()
    producer = _producer()
    from services.historian.client import get_connection

    published = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT outbox_id, payload
                FROM {OUTBOX_TABLE}
                WHERE sync_status IN ('pending', 'failed')
                ORDER BY outbox_id ASC
                LIMIT %s
                FOR UPDATE SKIP LOCKED
                """,
                (max(1, batch_size),),
            )
            rows = cur.fetchall()
            for outbox_id, payload in rows:
                record = dict(payload)
                try:
                    _publish_payload(producer, record)
                    cur.execute(
                        f"""
                        UPDATE {OUTBOX_TABLE}
                        SET sync_status='published', attempts=attempts + 1, published_at=now(), updated_at=now(), last_error=NULL
                        WHERE outbox_id = %s
                        """,
                        (outbox_id,),
                    )
                    published += 1
                    with _CACHE_LOCK:
                        _SYNC_STATE["published"] = int(_SYNC_STATE.get("published", 0) or 0) + 1
                        _SYNC_STATE["pending_outbox"] = max(0, int(_SYNC_STATE.get("pending_outbox", 0) or 0) - 1)
                        _SYNC_STATE["last_published_at"] = datetime.now(timezone.utc).isoformat()
                        _SYNC_STATE["status"] = "synced"
                        _SYNC_STATE["last_error"] = ""
                except Exception as exc:
                    logger.warning("threshold policy publish failed for %s: %s", outbox_id, exc)
                    cur.execute(
                        f"""
                        UPDATE {OUTBOX_TABLE}
                        SET sync_status='failed', attempts=attempts + 1, last_error=%s, updated_at=now()
                        WHERE outbox_id = %s
                        """,
                        (str(exc), outbox_id),
                    )
                    with _CACHE_LOCK:
                        _SYNC_STATE["status"] = "degraded"
                        _SYNC_STATE["last_error"] = str(exc)
        conn.commit()
    return published


def consume_policy_topic(
    *,
    stop_event: threading.Event,
    group_id: str,
    on_update: Callable[[dict[str, Any]], None] | None = None,
) -> None:
    try:
        consumer = _consumer(group_id)
    except Exception as exc:
        set_sync_error(str(exc))
        logger.warning("threshold policy consumer unavailable: %s", exc)
        return

    try:
        while not stop_event.is_set():
            message = consumer.poll(1.0)
            if message is None:
                continue
            if message.error():
                set_sync_error(str(message.error()))
                continue
            try:
                payload = json.loads(message.value().decode("utf-8"))
                if not isinstance(payload, dict):
                    raise ValueError("policy event must be a JSON object")
                policy = payload.get("policy") if isinstance(payload.get("policy"), dict) else payload
                if not isinstance(policy, dict):
                    raise ValueError("policy payload missing policy object")
                key = (str(policy.get("site_id", "")), str(policy.get("asset_id", "")), str(policy.get("tag", "")))
                current_version = get_cached_version(*key)
                incoming_version = int(policy.get("version", 0) or 0)
                if incoming_version < current_version:
                    continue
                cache_policy(policy)
                with _CACHE_LOCK:
                    _SYNC_STATE["status"] = "synced"
                    _SYNC_STATE["last_error"] = ""
                    _SYNC_STATE["last_consumed_at"] = datetime.now(timezone.utc).isoformat()
                    _SYNC_STATE["consumed"] = int(_SYNC_STATE.get("consumed", 0) or 0) + 1
                if on_update is not None:
                    on_update(policy)
            except Exception as exc:
                set_sync_error(str(exc))
                logger.warning("threshold policy consumer decode failure: %s", exc)
    finally:
        try:
            consumer.close()
        except Exception:
            pass


def start_policy_sync_workers(
    *,
    role: str,
    enable_relay: bool,
    initial_bootstrap: Callable[[], list[dict[str, Any]]] | None = None,
) -> tuple[threading.Event, list[threading.Thread]]:
    stop_event = threading.Event()
    threads: list[threading.Thread] = []

    if initial_bootstrap is not None:
        try:
            apply_threshold_snapshot(initial_bootstrap(), source=f"{role}:bootstrap", status="synced")
        except Exception as exc:
            set_sync_error(str(exc))

    consumer_thread = threading.Thread(
        target=consume_policy_topic,
        kwargs={
            "stop_event": stop_event,
            "group_id": f"{DEFAULT_GROUP_PREFIX}-{role}-{os.getpid()}",
            "on_update": None,
        },
        name=f"threshold-policy-consumer-{role}",
        daemon=True,
    )
    consumer_thread.start()
    threads.append(consumer_thread)

    if enable_relay:
        relay_thread = threading.Thread(
            target=_relay_loop,
            kwargs={"stop_event": stop_event},
            name=f"threshold-policy-relay-{role}",
            daemon=True,
        )
        relay_thread.start()
        threads.append(relay_thread)

    return stop_event, threads


def _relay_loop(*, stop_event: threading.Event) -> None:
    interval = max(0.5, float(os.getenv("THRESHOLD_POLICY_RELAY_INTERVAL_SECONDS", "2.0")))
    batch_size = max(1, int(os.getenv("THRESHOLD_POLICY_RELAY_BATCH_SIZE", "100")))
    while not stop_event.is_set():
        try:
            drain_policy_outbox(batch_size=batch_size)
        except Exception as exc:
            set_sync_error(str(exc))
            logger.warning("threshold policy relay failure: %s", exc)
        stop_event.wait(interval)

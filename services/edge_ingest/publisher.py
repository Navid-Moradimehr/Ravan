from __future__ import annotations

import logging
import time
from typing import Any

from confluent_kafka import Producer
from prometheus_client import Counter, Gauge, Histogram

from services.common.native_fastpath import encode_event_bundle
from services.common.normalize import to_legacy_iot_event
from services.common.stream_scope import stream_partition_key
from services.common.clock_quality import clock_quality_issue
from services.edge_ingest.model import DeadLetterEvent, IndustrialEvent, to_json_bytes, validate_event
from services.edge_ingest.settings import Settings
from services.edge_ingest.disk_spool import DiskEventSpool


events_total = Counter("edge_ingest_events_total", "Validated industrial events", ["protocol"])
dlq_total = Counter("edge_ingest_dlq_total", "Invalid industrial events", ["protocol"])
adapter_errors = Counter("edge_ingest_adapter_errors_total", "Adapter errors", ["protocol"])
adapter_reconnects = Counter("edge_ingest_reconnects_total", "Adapter reconnect attempts", ["protocol"])
last_success_epoch = Gauge("edge_ingest_last_success_epoch", "Last successful ingest timestamp", ["protocol"])
ingest_latency = Histogram("edge_ingest_latency_seconds", "Source-to-ingest latency", ["protocol"])
delivery_failures = Counter(
    "edge_ingest_delivery_failures_total", "Kafka delivery report failures", ["topic"]
)
overflow_total = Counter(
    "edge_ingest_overflow_total", "Records routed to DLQ by producer backpressure/oversize", ["reason"]
)
store_forward_spooled = Counter("edge_store_forward_spooled_total", "Events written to the local edge spool", ["topic"])
store_forward_replayed = Counter("edge_store_forward_replayed_total", "Events replayed from the local edge spool", ["topic"])
store_forward_pending = Gauge("edge_store_forward_pending", "Events currently pending in the local edge spool")
clock_violations = Counter(
    "edge_ingest_clock_violations_total",
    "Source timestamps outside the configured clock-quality bound",
    ["mode", "action"],
)

logger = logging.getLogger(__name__)


class EdgePublisher:
    def __init__(self, settings: Settings, batch_size: int = 256, flush_interval_ms: float = 1000.0) -> None:
        self.settings = settings
        self.producer = Producer(
            {
                "bootstrap.servers": settings.brokers,
                "client.id": "edge-ingest",
                "enable.idempotence": True,
                "acks": "all",
                "retries": 10,
                "batch.size": 16384,
                "linger.ms": 10,
                "compression.type": "lz4",
                "queue.buffering.max.messages": 100000,
                "message.max.bytes": settings.max_message_bytes,
            }
        )
        self._batch_size = batch_size
        self._flush_interval_ms = flush_interval_ms
        self._buffer: list[tuple[str, bytes, bytes]] = []
        self._last_flush = time.time()
        spool_dir = __import__("os").getenv("EDGE_STORE_FORWARD_DIR", "")
        self._spool = DiskEventSpool(spool_dir) if spool_dir else None

    @staticmethod
    def _delivery_report(err: Any, msg: Any) -> None:
        if err is not None:
            delivery_failures.labels(topic=msg.topic() if msg is not None else "unknown").inc()
            logger.warning("kafka delivery failed: %s", err)

    def _produce_safe(self, topic: str, key: bytes, value: bytes, origin: str = "unknown") -> None:
        if len(value) > self.settings.max_message_bytes:
            self._route_oversize(topic, key, value, origin)
            return
        while True:
            try:
                self.producer.produce(topic, key=key, value=value, on_delivery=self._delivery_report)
                return
            except BufferError:
                # Internal queue full: drain delivery reports and retry so the
                # caller experiences natural backpressure instead of crashing.
                self.producer.poll(0.5)
            except Exception as exc:
                if self._spool is not None:
                    self._spool.append(topic, key, value)
                    store_forward_spooled.labels(topic=topic).inc()
                    store_forward_pending.set(len(self._spool.read_all()))
                else:
                    self._route_oversize(topic, key, value, origin, error=type(exc).__name__)
                return

    def _replay_spool(self) -> None:
        if self._spool is None:
            return
        records = self._spool.read_all()
        remaining = list(records)
        for index, record in enumerate(records):
            topic, key, value = self._spool.decode(record)
            try:
                self.producer.produce(topic, key=key, value=value, on_delivery=self._delivery_report)
                remaining = remaining[index + 1 :]
                store_forward_replayed.labels(topic=topic).inc()
            except Exception:
                break
        self._spool.replace(remaining)
        store_forward_pending.set(len(remaining))

    def _route_oversize(
        self, topic: str, key: bytes, value: bytes, origin: str, error: str = "message_too_large"
    ) -> None:
        overflow_total.labels(reason=error).inc()
        dlq_total.labels(protocol="producer").inc()
        dlq_payload = {
            "source_protocol": "producer",
            "source_id": origin,
            "error": error,
            "payload": value.decode("utf-8", errors="replace")[:4096],
            "ts_ingest": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "schema_version": 1,
        }
        try:
            self.producer.produce(
                self.settings.dlq_topic,
                key=key,
                value=to_json_bytes(dlq_payload),
                on_delivery=self._delivery_report,
            )
        except Exception:
            self.producer.poll(0.5)

    def publish_raw(self, protocol: str, source_id: str, payload: dict[str, Any]) -> None:
        self._produce_safe(
            self.settings.raw_topic,
            f"{protocol}:{source_id}".encode("utf-8"),
            to_json_bytes(payload),
            origin=f"{protocol}:{source_id}",
        )

    def publish_event(self, payload: dict[str, Any]) -> None:
        protocol = str(payload.get("source_protocol", "unknown"))
        source_id = str(payload.get("source_id", "unknown"))
        self.publish_raw(protocol, source_id, payload)
        event, dlq = validate_event(payload)
        if dlq:
            self._buffer.append((self.settings.dlq_topic, source_id.encode("utf-8"), to_json_bytes(dlq)))
            dlq_total.labels(protocol=protocol).inc()
        else:
            assert event is not None
            event_dict = event.model_dump(mode="json")
            clock_issue = clock_quality_issue(
                event.ts_source,
                max_offset_seconds=max(self.settings.max_clock_offset_seconds, 0.0),
            )
            if clock_issue:
                mode = self.settings.clock_mode if self.settings.clock_mode in {"observe", "warn", "reject"} else "observe"
                action = "rejected" if mode == "reject" else "accepted"
                clock_violations.labels(mode=mode, action=action).inc()
                if mode == "reject":
                    rejected = DeadLetterEvent(
                        source_protocol=event.source_protocol,
                        source_id=event.source_id,
                        error=f"clock_policy_reject: {clock_issue}",
                        payload=event_dict,
                    )
                    self._buffer.append(
                        (self.settings.dlq_topic, event.source_id.encode("utf-8"), to_json_bytes(rejected))
                    )
                    dlq_total.labels(protocol=event.source_protocol).inc()
                    self._maybe_flush()
                    return
                if mode == "warn":
                    logger.warning("clock quality warning for %s: %s", event.source_id, clock_issue)
            bundle = encode_event_bundle(event_dict)
            if bundle is None:
                key = stream_partition_key(event_dict)
                normalized_bytes = to_json_bytes(event_dict)
                legacy_bytes = to_json_bytes(to_legacy_iot_event(event_dict))
            else:
                key, normalized_bytes, legacy_bytes = bundle
            self._buffer.append((self.settings.normalized_topic, key, normalized_bytes))
            self._buffer.append((self.settings.legacy_topic, key, legacy_bytes))
            events_total.labels(protocol=event.source_protocol).inc()
            last_success_epoch.labels(protocol=event.source_protocol).set(time.time())
            observe_latency(event)

        self._maybe_flush()

    def _maybe_flush(self) -> None:
        now = time.time()
        elapsed_ms = (now - self._last_flush) * 1000
        if len(self._buffer) >= self._batch_size or elapsed_ms >= self._flush_interval_ms:
            self._flush_buffer()

    def _flush_buffer(self) -> None:
        self._replay_spool()
        for topic, key, value in self._buffer:
            self._produce_safe(topic, key, value, origin="batch")
        self._buffer.clear()
        self.producer.poll(0)
        self._last_flush = time.time()

    def flush(self) -> None:
        self._flush_buffer()
        self.producer.flush(10)


def observe_latency(event: IndustrialEvent) -> None:
    try:
        source_epoch = time.mktime(time.strptime(event.ts_source[:19], "%Y-%m-%dT%H:%M:%S"))
        ingest_latency.labels(protocol=event.source_protocol).observe(max(time.time() - source_epoch, 0))
    except Exception:
        return

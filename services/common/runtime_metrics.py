from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from prometheus_client import Counter, Gauge, Histogram
except Exception:  # pragma: no cover - metrics are optional
    Counter = Gauge = Histogram = None  # type: ignore[assignment]


def _noop_metric():
    class _Noop:
        def labels(self, *args: Any, **kwargs: Any) -> "_Noop":
            return self

        def set(self, *args: Any, **kwargs: Any) -> None:
            pass

        def observe(self, *args: Any, **kwargs: Any) -> None:
            pass

        def inc(self, *args: Any, **kwargs: Any) -> None:
            pass

    return _Noop()


if Counter is not None and Gauge is not None and Histogram is not None:
    historian_query_latency = Histogram(
        "datastream_historian_query_latency_seconds",
        "Historian query latency by table and operation",
        ["table", "operation"],
    )
    historian_result_size = Histogram(
        "datastream_historian_result_size",
        "Historian query result size by table",
        ["table"],
    )
    broker_consumer_lag = Gauge(
        "datastream_broker_consumer_lag_messages",
        "Kafka consumer lag in messages for each topic/partition",
        ["service", "topic", "partition"],
    )
    websocket_delivery_lag = Histogram(
        "datastream_websocket_delivery_lag_seconds",
        "Delay between event timestamp and WebSocket delivery",
        ["channel"],
    )
    federation_lag = Gauge(
        "datastream_federation_lag_messages",
        "Federation transport lag in messages",
        ["topic"],
    )
    fanout_batches = Counter(
        "datastream_fanout_batches_total",
        "Sink batches completed by fan-out worker",
        ["service", "topic", "status"],
    )
    fanout_events = Counter(
        "datastream_fanout_events_total",
        "Events accepted or rejected by fan-out worker",
        ["service", "topic", "status"],
    )
    fanout_write_latency = Histogram(
        "datastream_fanout_write_latency_seconds",
        "Sink write latency by fan-out worker",
        ["service", "topic"],
    )
else:  # pragma: no cover - fallback path
    historian_query_latency = _noop_metric()
    historian_result_size = _noop_metric()
    broker_consumer_lag = _noop_metric()
    websocket_delivery_lag = _noop_metric()
    federation_lag = _noop_metric()
    fanout_batches = _noop_metric()
    fanout_events = _noop_metric()
    fanout_write_latency = _noop_metric()


def observe_historian_query(table: str, operation: str, duration_seconds: float, result_count: int) -> None:
    historian_query_latency.labels(table=table, operation=operation).observe(duration_seconds)
    historian_result_size.labels(table=table).observe(result_count)


def set_consumer_lag(service: str, topic: str, partition: int, lag_messages: int) -> None:
    broker_consumer_lag.labels(service=service, topic=topic, partition=str(partition)).set(max(lag_messages, 0))


def observe_websocket_delivery(channel: str, event: dict[str, Any]) -> None:
    timestamp = event.get("ts_ingest") or event.get("timestamp") or event.get("processed_at") or event.get("time")
    if not timestamp:
        return
    try:
        parsed = datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
    except Exception:
        return
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    lag = max((datetime.now(timezone.utc) - parsed).total_seconds(), 0.0)
    websocket_delivery_lag.labels(channel=channel).observe(lag)


def observe_websocket_batch_delivery(channel: str, events: list[dict[str, Any]]) -> None:
    if not events:
        return
    observe_websocket_delivery(channel, events[0])


def set_federation_lag(topic: str, lag_messages: int) -> None:
    federation_lag.labels(topic=topic).set(max(int(lag_messages), 0))


def observe_fanout_write(
    service: str,
    topic: str,
    event_count: int,
    accepted_count: int,
    duration_seconds: float,
    *,
    status: str = "success",
) -> None:
    """Record bounded stage metrics for a sink batch."""
    fanout_batches.labels(service=service, topic=topic, status=status).inc()
    fanout_events.labels(service=service, topic=topic, status="accepted").inc(max(accepted_count, 0))
    rejected = max(event_count - accepted_count, 0)
    if rejected:
        fanout_events.labels(service=service, topic=topic, status="rejected").inc(rejected)
    fanout_write_latency.labels(service=service, topic=topic).observe(max(duration_seconds, 0.0))

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

try:
    from prometheus_client import Gauge, Histogram
except Exception:  # pragma: no cover - metrics are optional
    Gauge = Histogram = None  # type: ignore[assignment]


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


if Gauge is not None and Histogram is not None:
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
else:  # pragma: no cover - fallback path
    historian_query_latency = _noop_metric()
    historian_result_size = _noop_metric()
    broker_consumer_lag = _noop_metric()
    websocket_delivery_lag = _noop_metric()
    federation_lag = _noop_metric()


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

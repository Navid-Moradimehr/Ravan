# Edge Ingest Backpressure

## Context

The edge ingestion layer reads from industrial protocols (MQTT, OPC UA, Modbus)
and publishes to Kafka. Two overload risks existed:

1. The confluent-kafka producer's internal queue can fill (BufferError) when the
   broker is slow or unavailable, crashing the adapter.
2. The MQTT connector produced to Kafka directly from the paho network thread,
   coupling broker backpressure to the MQTT client.

## Decision

- **Producer backpressure**: `EdgePublisher._produce_safe` retries on
  `BufferError` after draining delivery reports, and routes oversize messages
  (above `EDGE_MAX_MESSAGE_BYTES`) to the DLQ.
- **MQTT decoupling**: decoded payloads are enqueued onto a bounded
  `asyncio.Queue` (`EDGE_MQTT_QUEUE_SIZE`) and drained on the event loop. On
  queue-full, the message is routed to the DLQ and an overflow counter is
  bumped.

## Data Flow

```
paho network thread -> on_message -> json decode -> bounded asyncio.Queue
                                                          |
                                                          v
                                                   _drain_queue (event loop)
                                                          |
                                                          v
                                                   EdgePublisher.publish_event
                                                          |
                                              _produce_safe (retry / DLQ)
```

## Observability

- `edge_ingest_delivery_failures_total{topic}`
- `edge_ingest_overflow_total{reason=message_too_large|mqtt_queue_full}`
- `edge_ingest_dlq_total{protocol}`

## Settings

- `EDGE_MQTT_QUEUE_SIZE` (default 10000)
- `EDGE_MAX_MESSAGE_BYTES` (default 1048576)

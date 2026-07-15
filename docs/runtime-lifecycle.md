# Runtime Lifecycle and Downtime Handling

The platform treats telemetry gaps as part of the data contract. It does not
invent measurements while a line is stopped, and it does not interpret every
gap as a machine fault.

## Planned Stop

For a production schedule, operators disable the relevant source connections
or stop the site runtime during the planned non-production window. The
historian remains intact and the gap is visible in trend queries. When the
runtime starts again, enabled connectors reconnect, Kafka resumes from its
consumer offsets, and Flink resumes keyed state from its checkpoint when
checkpoint storage is configured.

The source-health contract now classifies stopped sources as
`planned_downtime` when the operator supplies that intent. This prevents a
scheduled night or weekend stop from being presented as an unexpected incident.

## Unplanned Interruption

If a PLC, sensor, broker connection, network path, or process fails, the
connector reports `error` or `reconnecting`. The lifecycle diagnostics classify
the source as `interrupted` or `recovering` after the configured expected event
interval expires. The endpoint is:

```text
GET /api/v1/observability/source-health?expected_interval_seconds=10
```

The response retains the existing connection state and adds `lifecycle`,
`last_success_at`, `last_success_age_seconds`, `stale_after_seconds`, and
`planned` fields. The default stale threshold is three expected intervals;
operators should set the query value to match the source sampling period.

During an interruption, Kafka-backed consumers retain offsets, the edge
connector retries where the protocol supports reconnect, disk store-and-forward
can buffer configured edge traffic, and historian writes remain idempotent on
replay. Events that cannot be validated or delivered are routed to the
existing DLQ/error metrics rather than silently fabricated.

## Recovery

When a valid event arrives again, the source returns to `running`, its last
successful timestamp is updated, and the normal processing, historian,
dashboard, and AI paths continue. A gap is therefore a real temporal property
of the dataset and can be excluded or labeled by downstream analytics.

## What Remains Operator-Owned

The platform does not infer a company's production calendar, maintenance
schedule, PLC fail-safe policy, retention period, or acceptable outage window.
Operators must configure source sampling expectations, planned stop intent,
Kafka retention, checkpoint/object-storage paths, and alert thresholds for each
site. This keeps the core behavior portable across factories, utilities,
energy sites, and other industrial deployments.

## Does Reconnection Need a UI Scheduler?

No. Reconnection should be automatic platform behavior, not a schedule that an
operator has to maintain. Protocol adapters should retry with bounded,
protocol-appropriate backoff, and the runtime should expose reconnecting,
recovering, interrupted, and running states. A fixed user-configured
"reconnect every N minutes" control would make recovery slower and would not
work well across OPC UA, MQTT, Modbus, and HTTP sources.

This matches current industrial edge patterns. Azure IoT Edge uses a module
restart policy and recommends exponential-backoff reconnect logic. AWS IoT
SiteWise Edge continues local collection during outages, buffers data, and
publishes it after connectivity returns. Their operator settings cover
deployment state, buffering, destinations, and monitoring rather than a
periodic reconnect timer.

The current release therefore does not add a reconnection scheduler UI. The
existing source enable/disable controls and source-health endpoint are enough
for normal operation. A later lightweight maintenance-window UI is justified
when operators need to label planned outages or suppress incident alerts. It
should create planned-downtime metadata and never replace a plant's MES,
maintenance calendar, or safety system.

References:

- [Azure IoT Edge module deployment and restart policy](https://learn.microsoft.com/en-us/azure/iot-edge/module-composition)
- [Azure IoT Edge troubleshooting and exponential-backoff reconnects](https://learn.microsoft.com/en-us/azure/iot-edge/troubleshoot-common-errors)
- [AWS IoT SiteWise Edge gateways and offline operation](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/gateways.html)
- [AWS IoT SiteWise buffered destinations](https://docs.aws.amazon.com/iot-sitewise/latest/userguide/destinations-buffered.html)

# Source Connection And Deployment

This note tracks the deployment boundary for plant sources.

## Platform-owned

- Versioned source connection contract
- Persisted connection registry
- Credential-reference validation
- Connection list and lifecycle APIs
- Bounded TCP diagnostics
- Multiple registry-backed source descriptors
- Legacy environment-variable fallback
- Canonical event and Kafka contracts

## User-owned

- PLC and gateway IP addresses
- OPC UA certificates and trust policy
- MQTT and Modbus credentials
- Firewall and OT/IT routing
- OPC UA nodes and Modbus register maps
- Asset, line, and site topology
- External Kafka, MQTT, AMQP, MinIO, S3, and SMTP accounts
- Authentication, authorization, SSO, and reverse proxy policy

## Connection flow

```text
User-owned device/network
        -> connection definition
        -> bounded test
        -> source mapping
        -> enabled edge source
        -> industrial.raw
        -> validation/normalization
        -> industrial.normalized
        -> processor/Flink
        -> historian, lakehouse, AI, and external sinks
```

## Current implementation state

The Integrations page can create source metadata and run a non-ingesting connection test. The edge runtime loads enabled registry records when present and otherwise preserves the legacy environment-variable deployment.

Enabled mappings are applied to the emitted canonical event before validation. Raw source payloads remain available on the raw topic for replay and troubleshooting.

The connection API now offers a bounded read-only OPC UA preview and accepts declarative Modbus register entries. Full Sparkplug B binary activation, richer register-map editing, durable health history, and end-to-end connector task orchestration remain future work.

The edge runtime exposes `edge_source_state` and `edge_source_last_success_epoch` Prometheus metrics labeled by connection ID, protocol, and site. The current state is live; long-term history remains the responsibility of Prometheus retention or a future operational store.

Sink routing metadata is available through `/api/v1/sinks` and is stored at
`DATASTREAM_SINK_ROUTING_PATH`. It selects the existing `historian`, `kafka`,
or `lakehouse` implementations without adding a service. `FANOUT_SINKS`
continues to work and takes precedence when set. Route changes require a
fan-out restart; `credential_ref` values are references only and no secret
material is accepted.

Sparkplug B uses TahUtils/Eclipse Tahu protobuf parsing in explicit Sparkplug mode. JSON MQTT remains a separate source mode.

Set `EDGE_STORE_FORWARD_DIR` to enable the optional durable local edge spool. Mount it on persistent storage. The spool covers synchronous Kafka publication failures and replays pending records on later flushes; it does not replace broker replication or backups.

## Security boundary

The registry never accepts raw password, token, secret, private-key, or API-key fields. Use Docker secrets, Kubernetes Secrets, Vault, environment variables, or another operator-controlled mechanism and store only a reference in the platform.

## Outbound delivery boundary

UI-created webhooks are persisted and attached to the alert webhook runtime. A generic notification webhook follows the same path. Email metadata is not an SMTP account; the operator must provide an Apprise or SMTP-capable deployment configuration before it can deliver.

Notification status includes a bounded, redacted delivery ledger for webhook
and Apprise attempts. It is intended for diagnostics and does not provide
durable asynchronous retry after process failure. A site that needs that
guarantee can supply its own queue or notification gateway.

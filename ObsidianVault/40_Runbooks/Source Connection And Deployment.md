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

The source-connection panel is metadata-only by design. It stores the connection contract, not the secret contents. The app should not browse arbitrary secret files or import a whole `.env` file. Operators should provide named credential references from their own secret store, and each source should point at a specific named entry even if several credentials live in one file.

This keeps the open-source deployment model portable and matches common industrial practice: the platform owns connection metadata and validation, while the deployment environment owns secret material and filesystem access.

Enabled mappings are applied to the emitted canonical event before validation. Raw source payloads remain available on the raw topic for replay and troubleshooting.

Mapping health is also tracked at runtime. If mappings are configured but do not match live traffic, the source-health snapshot records mapping-match and mapping-miss counts so operators can distinguish a valid connection from a semantically misaligned one.

The connection API now offers a bounded read-only OPC UA preview and accepts declarative Modbus register entries. Full Sparkplug B binary activation, richer register-map editing, durable health history, and end-to-end connector task orchestration remain future work.

The edge runtime exposes `edge_source_state`, `edge_source_last_success_epoch`, and mapping-match/mapping-miss counters labeled by connection ID, protocol, and site. With `EDGE_SOURCE_HEALTH_HISTORY_PATH`, state transitions are retained in a bounded local file and exposed through `/api/v1/observability/source-health`; repeated successful reads are not recorded individually.

Sink routing metadata is available through `/api/v1/sinks` and is stored at
`DATASTREAM_SINK_ROUTING_PATH`. It selects the existing `historian`, `kafka`,
or `lakehouse` implementations without adding a service. `FANOUT_SINKS`
continues to work and takes precedence when set. When `SINKS` is unset,
fan-out detects route-file changes between batches and reloads the existing
sink implementations without container recreation. `credential_ref` values
are references only and no secret material is accepted. They are not file
paths for the app to browse.

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

## Flink and sink ownership

The distributed Flink path is the larger-deployment stream processor. It
handles keyed, stateful processing with checkpoints, while the Python path is
the local fallback and development path. Both keep the same canonical event
contract so downstream services do not have to care which runtime produced a
record.

Sink ownership is split the same way:

- historian sink = operational system of record
- Kafka sink = downstream stream/export target
- lakehouse sink = optional Iceberg/MinIO archive for AI and batch analysis

The historian sink is the default. Kafka and lakehouse are already integrated
in the codebase, but they are optional fan-out targets enabled by route
metadata or `SINKS`, not hard requirements. Operators still own the endpoint
credentials and deployment-time settings for those sinks.

## Release update boundary

The platform includes an opt-in, read-only update check. When enabled, the API
and dashboard compare the running version with a JSON manifest published on
GitHub or an internal mirror and show a toast with the release version. It
never downloads, executes, replaces, or migrates the running deployment.

This is intentional for industrial installations: update approval, artifact
verification, backup, drain, migration, restart, and rollback belong to the
future installer/update agent and the site's change-control process. Air-gapped
deployments leave `DATASTREAM_UPDATE_CHECK_ENABLED=false`.

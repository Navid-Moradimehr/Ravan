# Source Connections And Deployment Ownership

## What the platform owns

The platform owns the connection contract, source identity, protocol adapter interfaces, validation, canonical event conversion, Kafka publication, dead-letter routing, runtime health, historian sinks, replay, and delivery contracts.

The platform does not own plant credentials, certificates, firewall rules, PLC programming, register-map correctness, company topology, external broker accounts, SMTP accounts, cloud credentials, or authentication and authorization policy.

## First-time connection workflow

1. Install the platform on an edge or plant server that can reach the OT network.
2. Open Integrations and create a source connection.
3. Select OPC UA, MQTT, Modbus TCP, Modbus RTU, REST Pull, HTTP Push, or a reference-only source type.
4. Enter the site ID. Enter an endpoint when the source reaches out to a device/API; HTTP Push receives a generated platform endpoint.
5. Follow the five steps in the editor: Identity, Connectivity, Discover/sample, Map data, and Review/enable. OPC UA node IDs, MQTT topic/QoS, Modbus register rows, RTU serial settings, and REST request/JSON paths are collected through normal fields.
6. Add credential references where required. Use `env://NAME` or `file://path` for secret values and `path://path` for certificate/key file paths. The registry stores references only.
7. Add source-to-asset mappings in the mapping table.
8. Save, run Validate, run Test, optionally Preview discovered fields, then press Enable in the same UI. No manual API call is required for supported runtime protocols.
9. Verify `industrial.raw`, `industrial.normalized`, the historian, and the edge metrics before adding dashboards or alerts.

The source-connection panel is a desired-state editor backed by internal metadata. Users do not edit backend code, Compose files, or raw registry JSON. The edge runtime consumes the saved definition and reconciles connector tasks without a container restart. It does not browse or import a whole `.env` file and does not store passwords or certificates in the registry. A saved draft may be incomplete; Enable is the strict boundary and reports missing protocol fields.

If an operator keeps credentials in a secret manager, each connection should point at a separate named secret reference such as `secret://site-a/opcua/pump-01` or `secret://site-a/mqtt/broker-02`. If multiple credentials happen to live in the same file, the file is still the operator's secret store boundary; the platform should reference the specific entry name or key, not the file contents. That keeps the registry portable and avoids ambiguity when two sources share one file.

This is standard industrial practice for self-hosted tools: the platform owns connection metadata and runtime state, while the deployment environment owns secret material and file access.

## Configuration compatibility

The persisted registry is stored at `DATASTREAM_CONNECTION_REGISTRY_PATH`. Docker Compose mounts this state at `/data/connection-registry.json` through the `api-data` volume.

If no enabled registry connections exist, the edge runtime creates the legacy sources from `EDGE_PROTOCOLS`, `OPCUA_ENDPOINT`, `OPCUA_NODES`, `MQTT_HOST`, `MQTT_TOPIC`, `MODBUS_HOST`, and related variables. Existing deployments therefore continue to work while registry-managed sources are introduced.

Editing a source preserves its current runtime state. If the connection was enabled, the update keeps it enabled. If the source was retired, the update keeps it archived until an operator restores it explicitly.

Each registry source has a stable `connection_id`, site boundary, source protocol, endpoint, configuration version, mappings, and runtime state. Secrets are represented only by references. The registry rejects password, token, secret, private-key, and API-key fields. `credential_refs` provides separate references for username, password, OPC UA certificates, and MQTT TLS files.

When an enabled source has mappings, the edge runtime applies the first matching mapping to the emitted event before canonical validation. Mapping can set asset, tag, site, line, unit, scale, and offset. The raw topic still receives the source payload, so mapping changes do not erase the original source record.

Mapping health is also tracked at runtime. If mappings are configured but do not match live traffic, the source-health snapshot records mapping-match and mapping-miss counts so operators can distinguish a valid connection from a semantically misaligned one.

Retiring a source does not erase it. The registry keeps the record, marks it as retired, and removes it from the active runtime path. This is the preferred way to decommission a sensor, PLC, gateway, or API endpoint while preserving audit and replacement history.

## Protocol notes

OPC UA sources use the configured endpoint and node list. The connection workflow provides a bounded read-only preview endpoint that browses tags or reads a selected node without enabling ingestion. Discovery is an operation in the OPC UA workflow, not a separate source protocol. Selected node IDs can be persisted through `POST /api/v1/connections/{connection_id}/opcua/browse-selection`; the registry stores the node IDs and a `browse_nodes` copy without storing certificate material. Certificate, private-key, CA, and optional security-string values remain deployment-owned references.

MQTT sources subscribe to configured topic filters with the existing QoS, TLS, reconnect, bounded queue, and dead-letter behavior. Sparkplug B sources use the optional pinned TahUtils/Eclipse Tahu protobuf decoder when `source_protocol` is `sparkplug_b` or `config.payload_mode` is `sparkplug_b`. Birth and death topics update source health and produce a canonical `__sparkplug_lifecycle__` state event; ordinary JSON MQTT is not automatically equivalent to binary Sparkplug B.

Modbus sources accept declarative register entries with address, tag, unit, scale, offset, and unit ID. A registry-managed source must provide an explicit register map; it never silently uses demo registers. Datatype, byte order, word order, input/holding register selection, and richer register-map editing remain user-owned configuration or future UI work. The platform cannot safely infer those from a device endpoint.

REST Pull is a runtime source. Configure an HTTP(S) endpoint, GET or POST, bounded poll interval and timeout, optional deployment-owned authentication reference, response records path, canonical field paths, and bounded pagination. Each record becomes a deterministic canonical event and uses the same Kafka, DLQ, lineage, processor, historian, and optional sink path as PLC telemetry. REST retries, page counts, records per poll, and request timeouts are bounded.

HTTP Push is a runtime ingress for gateways and applications that already own the outbound connection. After an `http_push` connection is enabled, post one event to `/api/v1/connections/<connection_id>/events` or up to 1,000 events to `/events/batch`. The route requires a registered enabled connection, stamps source/site lineage, uses the canonical ingest path, and deduplicates repeated `Idempotency-Key` or `event_id` values in the TimescaleDB-backed idempotency ledger. If durable storage is unavailable, the route fails closed instead of silently weakening deduplication. Authentication is deliberately left to the operator's reverse proxy or API boundary.

## Multi-site deployment options

For a plant-local deployment, run the edge service near the PLCs and write to a local Kafka and historian. For a centralized deployment, run one edge instance per site and forward selected Kafka topics or sink outputs to central Kafka, MinIO, S3, or Iceberg. Keep site IDs and source IDs in every event so central storage does not merge unrelated equipment.

For air-gapped sites, keep Kafka and historian local and export approved batches or replicated topics through the company-controlled transfer mechanism. The platform does not decide the company network boundary.

The edge runtime supports an opt-in local spool through `EDGE_STORE_FORWARD_DIR`. When Kafka publication fails synchronously, events are written as crash-tolerant JSONL records and retried on later flushes. Mount this directory on durable local storage. This does not replace Kafka replication or site backups.

## Authentication and authorization boundary

The API's mutation routes remain protected by the existing bearer-token middleware. This project does not prescribe an identity provider, SSO system, RBAC model, gateway, or reverse proxy. Operators may place Traefik, NGINX, Kong, an auth proxy, SSO, or an enterprise IAM integration in front of the API and dashboard according to site policy.

In Docker Compose, internal API-to-AI health checks use the service DNS name
`ai-gateway:8080`; host/browser access remains through the published host
ports.

## Webhooks and notifications

Webhooks created through the historian UI are persisted in the API data volume, can be tested and deleted, and are attached to the same outbound webhook runtime used by alarm delivery. Generic notification webhook destinations are attached to that runtime as well.

An email address alone is not an SMTP configuration. To deliver email, the operator must configure an Apprise URL or SMTP-capable provider through the operator-owned deployment environment. The notification registry records this distinction instead of pretending that an address is automatically deliverable.

The API notification status endpoint also exposes a bounded recent delivery
ledger. It records whether webhook or Apprise delivery was attempted,
delivered, or failed, including retry count and HTTP status where applicable.
Destination labels are redacted and provider credentials are never written to
the ledger. This is operational visibility, not a durable asynchronous queue;
operators requiring guaranteed delayed delivery should place a user-managed
queue or notification service behind the configured provider.

## Sink routing

The normalized fan-out consumer supports the existing `historian`, `kafka`,
and `lakehouse` sink implementations. `FANOUT_SINKS` remains the
backward-compatible environment configuration. Alternatively, operators can
persist route metadata through `/api/v1/sinks`; the API stores it at
`DATASTREAM_SINK_ROUTING_PATH`, and fan-out loads enabled route types when
`SINKS` is not explicitly set. Route changes are detected between fan-out
batches and reload without container recreation. Route metadata contains no secrets;
`credential_ref` is only a reference to deployment-managed credentials. It is not a path to be scanned by the app and not a request for the UI to open arbitrary secret files.

The default sink is still the historian because that is the operational
system of record. Kafka and lakehouse sinks are already integrated, but they
are optional fan-out targets rather than the default path:

- historian sink = built-in operational storage
- Kafka sink = downstream stream/export target
- lakehouse sink = Iceberg/MinIO analytical archive for AI and batch use

The platform owns the sink contract and route metadata; the deployment owns
whether a given sink is enabled and how its credentials or endpoints are
supplied.

## Current status

- Implemented: versioned connection contract, persisted registry, secret-reference validation, list/create/update/delete/enable/disable APIs, bounded TCP diagnostics, Docker persistence, multiple registry-backed edge source descriptors, and legacy environment fallback.
- Implemented: per-source Prometheus health metrics labeled by connection, protocol, and site, plus runtime mapping-match and mapping-miss diagnostics.
- Implemented: draft lifecycle, protocol-specific activation readiness, REST Pull polling, HTTP Push single/batch ingress, bounded retries/pagination, deterministic REST event IDs, and the guided source editor.
- Implemented: bounded persistent source-health transition history, source delivery history at `/api/v1/observability/source-delivery`, durable HTTP Push idempotency, typed Modbus TCP and RTU datatype/byte/word-order decoding, and OPC UA security-string configuration hooks. In Compose, API-origin delivery records live in `/data`, while edge-origin records live on the shared edge volume and are merged by the API.

Validation evidence, 2026-07-16: 27 focused source/connector tests passed, the UI production build passed, and the complete Docker rebuild passed. A live Compose test ingested one HTTP Push event, restarted the API, resent the same idempotency key, and received `duplicate` without a second ingest. The full Python suite reached 671 passing tests; three unrelated release-gate tests remain environment-dependent because host-side `pg_dump`/`dropdb` tooling was unavailable, so backup safety was not weakened to hide that prerequisite.
- Partially implemented: full OPC UA trust-store provisioning/renewal and vendor-specific gateway compatibility, OAuth2/mTLS diagnostics beyond connector execution, Sparkplug command/rebirth orchestration, and deeper source-to-asset mapping UI.
- User-owned: credentials, certificates, network access, firewall rules, asset topology, register-map correctness, external storage, external brokers, SMTP, and authentication/authorization.
- Future: durable connector task orchestration, richer protocol diagnostics,
  durable HTTP Push idempotency across process restarts, and per-route delivery
  history. Source-health transition history and sink route refresh are
  implemented; a durable asynchronous notification queue remains intentionally
  deployment-owned.

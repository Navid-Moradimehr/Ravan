# Source Connections And Deployment Ownership

## What the platform owns

The platform owns the connection contract, source identity, protocol adapter interfaces, validation, canonical event conversion, Kafka publication, dead-letter routing, runtime health, historian sinks, replay, and delivery contracts.

The platform does not own plant credentials, certificates, firewall rules, PLC programming, register-map correctness, company topology, external broker accounts, SMTP accounts, cloud credentials, or authentication and authorization policy.

## First-time connection workflow

1. Install the platform on an edge or plant server that can reach the OT network.
2. Open Integrations and create a source connection.
3. Select OPC UA, MQTT, Modbus TCP, Modbus RTU, REST, or another supported source type.
4. Enter the endpoint and site ID.
5. Enter a credential reference such as `secret://plant-a/opcua/pump`; never enter a password in the connection config.
6. Save the source definition.
7. Run the connection test. This performs configuration validation and a bounded TCP reachability check. It does not publish data.
8. Add source-to-asset mappings in the connection definition or deployment manifest.
9. Enable the connection through the protected API or deployment workflow.
10. Verify `industrial.raw`, `industrial.normalized`, the historian, and the edge metrics before adding dashboards or alerts.

The current UI provides the connection definition and test surface. Full protocol-specific browse and register-map editing are the next extension points; existing environment variables remain supported.

## Configuration compatibility

The persisted registry is stored at `DATASTREAM_CONNECTION_REGISTRY_PATH`. Docker Compose mounts this state at `/data/connection-registry.json` through the `api-data` volume.

If no enabled registry connections exist, the edge runtime creates the legacy sources from `EDGE_PROTOCOLS`, `OPCUA_ENDPOINT`, `OPCUA_NODES`, `MQTT_HOST`, `MQTT_TOPIC`, `MODBUS_HOST`, and related variables. Existing deployments therefore continue to work while registry-managed sources are introduced.

Each registry source has a stable `connection_id`, site boundary, source protocol, endpoint, configuration version, mappings, and runtime state. Secrets are represented only by references. The registry rejects password, token, secret, private-key, and API-key fields.

When an enabled source has mappings, the edge runtime applies the first matching mapping to the emitted event before canonical validation. Mapping can set asset, tag, site, line, unit, scale, and offset. The raw topic still receives the source payload, so mapping changes do not erase the original source record.

## Protocol notes

OPC UA sources use the configured endpoint and node list. The connection workflow now provides a bounded read-only preview endpoint that browses tags or reads a selected node without enabling ingestion. Subscription management, certificate trust configuration, and persistent browse selection remain future work.

MQTT sources subscribe to configured topic filters with the existing QoS, TLS, reconnect, bounded queue, and dead-letter behavior. Sparkplug B sources use the optional pinned TahUtils/Eclipse Tahu protobuf decoder when `source_protocol` is `sparkplug_b` or `config.payload_mode` is `sparkplug_b`. Ordinary JSON MQTT is not automatically equivalent to binary Sparkplug B.

Modbus sources accept declarative register entries with address, tag, unit, scale, offset, and unit ID. Datatype, byte order, word order, input/holding register selection, and richer register-map editing remain user-owned configuration or future UI work. The platform cannot safely infer those from a TCP endpoint.

## Multi-site deployment options

For a plant-local deployment, run the edge service near the PLCs and write to a local Kafka and historian. For a centralized deployment, run one edge instance per site and forward selected Kafka topics or sink outputs to central Kafka, MinIO, S3, or Iceberg. Keep site IDs and source IDs in every event so central storage does not merge unrelated equipment.

For air-gapped sites, keep Kafka and historian local and export approved batches or replicated topics through the company-controlled transfer mechanism. The platform does not decide the company network boundary.

## Authentication and authorization boundary

The API's mutation routes remain protected by the existing bearer-token middleware. This project does not prescribe an identity provider, SSO system, RBAC model, gateway, or reverse proxy. Operators may place Traefik, NGINX, Kong, an auth proxy, SSO, or an enterprise IAM integration in front of the API and dashboard according to site policy.

## Webhooks and notifications

Webhooks created through the historian UI are persisted in the API data volume, can be tested and deleted, and are attached to the same outbound webhook runtime used by alarm delivery. Generic notification webhook destinations are attached to that runtime as well.

An email address alone is not an SMTP configuration. To deliver email, the operator must configure an Apprise URL or SMTP-capable provider through the operator-owned deployment environment. The notification registry records this distinction instead of pretending that an address is automatically deliverable.

## Current status

- Implemented: versioned connection contract, persisted registry, secret-reference validation, list/create/update/delete/enable/disable APIs, bounded TCP diagnostics, Docker persistence, multiple registry-backed edge source descriptors, and legacy environment fallback.
- Implemented: per-source Prometheus health metrics labeled by connection, protocol, and site.
- Partially implemented: MQTT Sparkplug B activation, richer Modbus register maps, durable health history, and source-to-asset mapping UI.
- User-owned: credentials, certificates, network access, firewall rules, asset topology, register-map correctness, external storage, external brokers, SMTP, and authentication/authorization.
- Future: durable connector task orchestration, richer protocol diagnostics, store-and-forward across Kafka outages, and configurable sink routing.

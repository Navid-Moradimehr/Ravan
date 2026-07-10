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

Protocol browsing, full Sparkplug B activation, configurable Modbus register maps, durable per-source health, and end-to-end connector task orchestration remain future work.

## Security boundary

The registry never accepts raw password, token, secret, private-key, or API-key fields. Use Docker secrets, Kubernetes Secrets, Vault, environment variables, or another operator-controlled mechanism and store only a reference in the platform.

## Outbound delivery boundary

UI-created webhooks are persisted and attached to the alert webhook runtime. A generic notification webhook follows the same path. Email metadata is not an SMTP account; the operator must provide an Apprise or SMTP-capable deployment configuration before it can deliver.

# Source Connection Walkthrough

This is the user-facing guide for connecting a PLC, sensor gateway, broker, or API source to the platform.

## 1. What you are setting up

You are creating a source record that says:

- which protocol to use
- which site it belongs to
- which endpoint or broker it should talk to
- which deployment-managed credential reference it should use
- which asset and tag mappings should be applied

The platform stores that as metadata. The actual secret material stays in the operator's secret store or deployment environment.

## 2. First-time setup flow

1. Open `Integrations`.
2. Create a source connection.
3. Choose the protocol, such as OPC UA, MQTT, Modbus TCP, Modbus RTU, REST, or Sparkplug B.
4. Enter the endpoint or broker address.
5. Enter the site ID.
6. Provide a `credential_ref` that points to a secret the operator already owns.
7. Save the source definition.
8. Run the connection test.
9. Add mappings if the source fields need to become asset or tag names.
10. Enable the source.

## 3. What happens after save

- the source appears in the `Integrations` page immediately
- the platform shows its protocol, endpoint, and configuration version
- the source still does not publish data until it is enabled

## 4. What the connection test tells you

- whether the configuration is valid
- whether the endpoint is reachable for network-based sources
- read-only preview for OPC UA
- configuration-only checks for file, dataset, or mock sources

## 5. What happens after enablement

1. source device or gateway
2. connector
3. canonical normalization
4. Kafka
5. processor or Flink
6. historian
7. optional fan-out sinks
8. UI and observability reads

## 6. Where the source shows up

- `Integrations` as saved source metadata
- source-health diagnostics and metrics, including mapping-match and mapping-miss counts when mappings are configured
- historian queries and trends
- dashboards, if you create a chart for its tag or asset
- Kafka UI, if you look at the relevant topic

## 7. What you still configure manually

- the real PLC or broker address
- the actual secret or certificate
- the register map or topic pattern
- the asset and tag mapping
- the dashboard layout
- the sink targets, if you want the data to leave the historian path

## 8. Read side versus write side

- collect once
- normalize once
- store once
- fan out to optional sinks when configured

Read side:

- historian trends
- historian SQL
- replay
- dashboards
- observability
- Kafka UI

## 9. Sink options

- historian
- Kafka
- lakehouse

Historian is the default operational sink.
Kafka and lakehouse are optional fan-out targets.

## 10. Flink in this flow

Use it when you need keyed processing, rolling windows, checkpointing, restart-safe state, and multi-node scaling.

## 11. Common mistakes

- putting real secrets into app config instead of a secret store
- expecting a source to produce dashboards before data exists
- forgetting to enable the source after saving it
- mapping the wrong asset or tag
- assuming a source is healthy just because the registry entry exists

## 12. What errors you should expect

- missing or invalid source name, protocol, site, or endpoint returns a validation error
- malformed mapping rows return field-level validation errors
- unreachable endpoints return a failed connection test result
- unknown connection IDs return `not found`
- sink route failures are logged and can leave the historian as the safe default

Some mismatches are intentionally softer:

- a missing `credential_ref` is not always an error because some deployments use legacy environment variables or other operator-owned secret paths
- a mapping that does not match incoming source fields does not block ingest, it just does not apply

That means the platform catches broken config, and it now exposes mapping misses in source-health state so operators can see when a connection is valid but semantically misaligned.

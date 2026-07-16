# Source Connection Walkthrough

This is the user-facing guide for connecting a PLC, sensor gateway, broker, or API source to the platform.

## 1. What you are setting up

You are not wiring the platform directly to a secret file or a whole `.env` dump.
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
3. Choose the protocol, such as OPC UA, MQTT, Modbus TCP, Modbus RTU, REST Pull, HTTP Push, or Sparkplug B.
4. Complete Identity, Connectivity, Discover/sample, Map data, and Review/enable. REST exposes method, poll interval, auth mode, pagination, and dotted JSON field paths as fields rather than requiring a connector code change.
5. Enter the endpoint or broker address when the platform polls or connects outward. HTTP Push receives a generated endpoint after activation.
6. Enter the site ID and credential references if required. Use `env://NAME` or `file://path` for secret values and `path://path` for certificate/key files.
7. Add mappings through the mapping table if the source fields need to become canonical asset or tag names.
8. Save the source definition as a draft, run Validate, run Test, and use Preview when the protocol supports discovery.
9. Press Enable in the same source row. The edge runtime reconciles the desired state automatically.

## 3. What happens after save

After the save:

- the source appears in the `Integrations` page immediately
- the platform shows its protocol, endpoint, and configuration version
- the source still does not publish data until it is enabled

The source list shows five registered sources by default. Select **Show all
sources** to view up to twenty sources per page and navigate additional pages.

The new source does not automatically create dashboards or historical plots. Those appear only after data starts flowing and the user chooses how to visualize it.

## 4. What the connection test tells you

The connection test checks two things:

- whether the configuration is valid
- whether the endpoint is reachable for network-based sources

For OPC UA, the platform can also provide a read-only preview of tags or a node read.
For Modbus, it can validate the declared register-style configuration.
For REST Pull, the test performs a bounded HTTP request without publishing data. For HTTP Push, the test returns the generated ingest endpoint. For file, dataset, or mock sources, the test is configuration-only because there is no live runtime endpoint.

## 5. What happens after enablement

Once the source is enabled, the edge runtime starts reading it.

The data path is:

1. source device or gateway
2. connector
3. canonical normalization
4. Kafka
5. processor or Flink
6. historian
7. optional fan-out sinks
8. UI and observability reads

## 6. Where the source shows up

After enablement and event flow, the source can show up in:

- `Integrations` as saved source metadata
- source-health diagnostics and metrics, including mapping-match and mapping-miss counts when a source has mappings
- the historian page may also show a warning if live traffic is arriving but no mapping has matched yet
- historian queries and trends
- dashboards, if you create a chart for its tag or asset
- Kafka UI, if you look at the relevant topic

The platform does not automatically invent a chart for every source.
That is usually an operator choice.

## 7. What you still configure manually

The platform still expects the operator to own:

- the real PLC or broker address
- the actual secret or certificate
- the register map or topic pattern
- the asset and tag mapping
- the dashboard layout
- the sink targets, if you want the data to leave the historian path

## 8. Read side versus write side

The platform is intentionally strong on the write side:

- it collects data once
- it normalizes once
- it stores once
- it fans out to optional sinks when configured

The read side is then handled through:

- historian trends
- historian SQL
- replay
- dashboards
- observability
- Kafka UI

If you need a central BI or training dataset, use the lakehouse sink or another downstream consumer.

## 9. Sink options

The platform already supports these sink targets:

- historian
- Kafka
- lakehouse

Historian is the default operational sink.
Kafka and lakehouse are optional fan-out targets.

## 10. Flink in this flow

Flink is the stateful processing path for larger deployments.
Use it when you need:

- keyed processing
- rolling windows
- checkpointing
- restart-safe state
- multi-node scaling

For local development, the Python fallback path remains available.

## 11. Common mistakes

- putting real secrets into the app config instead of a secret store
- expecting a source to produce dashboards before data exists
- forgetting to enable the source after saving it
- mapping the wrong asset or tag
- assuming a source is healthy just because the registry entry exists

## 12. Practical rule

If the source is saved, it exists as metadata.
If it is enabled, the edge can use it.
If data is flowing, the historian and read side can show it.

## 14. Editing and removing a source

Editing a source updates the saved connection in place and preserves its current runtime state.
If the source is already retired, editing updates the archived record but does
not bring it back online.

The usual edit flow is:

1. Open `Integrations`.
2. Click `Edit` on the source.
3. Change the endpoint, protocol settings, source ID, credential reference, or mappings.
4. Save the change.
5. Re-run `Validate` or `Test` if the protocol settings changed.

Removing a source now means retiring it, not erasing its history.

The retire flow is:

1. Open `Integrations`.
2. Click `Retire` on the source.
3. Confirm the action.
4. The source leaves the active runtime path and remains archived for audit and replacement history.

If you later need the same logical connection again, restore the archived record from the API boundary and then validate and enable it again.

## 13. What errors you should expect

The platform already reports some problems clearly:

- missing or invalid source name, protocol, site, or endpoint returns a validation error
- malformed mapping rows return field-level validation errors
- unreachable endpoints return a failed connection test result
- unknown connection IDs return `not found`
- sink route failures are logged and can leave the historian as the safe default

Some mismatches are intentionally softer:

- a missing `credential_ref` is not always an error because some deployments use legacy environment variables or other operator-owned secret paths
- a mapping that does not match incoming source fields does not block ingest, it just does not apply

That means the platform is good at catching broken config, and it now surfaces mapping misses in source-health state so operators can see when a connection is valid but semantically misaligned.

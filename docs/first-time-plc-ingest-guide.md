# First-Time PLC And Sensor Ingest Guide

This guide is for a first-time user who wants to connect PLCs and sensors from a manufacturing site into Local Stream Engine.

It covers:

- what to configure first
- how each protocol connector works
- how several PLCs and sensors stay separate but still correlate later
- what the historian stores
- what the dashboard shows
- what Apache Flink does in the platform

For the operator-facing source registry and deployment boundary, see `docs/source-connection-and-deployment.md`. That document is the canonical explanation of how source metadata, credential references, and deployment-owned secrets fit together.

## 1. What The Platform Does Automatically

The platform already knows how to:

- read OPC UA, MQTT, Modbus TCP, Modbus RTU, and REST Pull sources
- accept tracked HTTP Push events from gateways and applications
- normalize different payload shapes into one internal industrial event format
- publish those events to Kafka topics
- send invalid messages to the dead-letter path
- store normalized events in the historian
- show live status in the dashboard
- score and enrich events in the processor and Flink paths

That means you do not need to build your own data pipeline from scratch. You mostly need to tell the platform:

- where the devices are
- which tags matter
- how to map them to assets
- which credentials and certificates to use

## 2. What The User Must Configure

Before connecting any device, prepare these items:

- PLC or gateway IP address
- port number
- protocol type
- node IDs, register maps, or topic names
- asset and tag mapping
- site and line names
- TLS certificates if the device requires them
- username/password or token if the gateway or broker requires it

The platform should not be handed a raw secret file to browse. Instead, the user should create a named secret in the deployment's secret store or environment and reference that name from the source definition. If two devices use different credentials from the same `.env` file, each source still gets its own `credential_ref` that points at a distinct key or named entry.

In this repo, the edge connector settings come from environment variables such as:

- `OPCUA_ENDPOINT`
- `OPCUA_NODES`
- `MODBUS_HOST`
- `MODBUS_PORT`
- `MQTT_HOST`
- `MQTT_PORT`
- `MQTT_TOPIC`
- `MQTT_QOS`
- `MQTT_WILL_TOPIC`
- `MQTT_CA_CERT`
- `MQTT_CERTFILE`
- `MQTT_KEYFILE`
- `EDGE_PROTOCOLS`

For real sites, these values usually come from:

- the PLC or gateway network inventory
- the plant automation team
- the controls engineer or OT engineer
- the gateway admin
- the local site profile or installer configuration

Do not hardcode them into the app. Keep them in the site config or local secret store. The app should carry the reference, not the secret material.

## 3. How The Data Flows

The main flow is:

1. A PLC or sensor publishes or exposes a value.
2. The connector reads it.
3. The connector converts it into the platform’s canonical event shape.
4. Kafka receives the event.
5. The processor or Flink job scores and enriches it.
6. The historian stores it.
7. The UI reads it from the historian and live streams.
8. Alerts, webhooks, AI summaries, and dashboards consume the same event stream later.

The key design point is that one source is not mixed with another source unless you explicitly correlate them later using asset metadata.

## 4. OPC UA Scenario

OPC UA is the best starting point for modern PLCs because it can expose a richer model than simple register polling.

### How to set it up

1. Open **Integrations** and select **OPC UA**.
2. Complete the Identity and Connectivity steps with the site and endpoint.
3. Use the read-only Preview workflow to browse the server, then copy selected node IDs into the source definition.
4. If the server uses certificates, provide credential references for the deployment-managed certificate and key.
5. Map each node to an asset and tag, save the draft, test it, and enable it.

### What happens in the platform

- The OPC UA connector reads the node values.
- Each reading becomes a normalized industrial event.
- The event preserves `source_protocol="opcua"` and a stable `source_id`.
- The historian stores the result.

### Can OPC UA carry processed data?

Yes.

Some OPC UA servers expose:

- raw sensor values
- calculated values
- quality bits
- aggregated variables
- PLC-side derived tags

The platform can ingest all of them. It does not require a value to be “raw” to store it. What matters is that you keep the source identity and tag name clear.

If you want to separate raw and calculated values, do this:

- keep raw nodes under raw tag names
- keep calculated nodes under derived tag names
- use separate `tag` names or a naming convention such as `temperature_raw` and `temperature_avg_10s`

That way the historian can store both, and later analytics can decide which one to use.

## 5. Modbus TCP Scenario

Use Modbus TCP when you have older PLCs, meters, or industrial devices that expose registers instead of a rich semantic model.

### How to set it up

1. Set `MODBUS_HOST` and `MODBUS_PORT`.
2. Define the register map for the values you want.
3. Map registers to tags and units.
4. Confirm the right scaling and byte order.

### What happens in the platform

- The connector polls the device.
- Register values are converted into industrial events.
- Each source keeps its own identity.
- The historian stores the normalized record.

### Common Modbus concerns

- byte order
- word order
- register offset mistakes
- shared-bus latency

Keep those details in the connector layer, not in the historian.

## 6. Modbus RTU Scenario

Use Modbus RTU for serial devices, RS-485 trunks, or legacy brownfield equipment.

### How to set it up

1. Configure the serial port and communication parameters.
2. Provide the register map.
3. Confirm the unit/slave id.
4. Keep the source identity unique per device.

### What happens in the platform

- The RTU client reads over serial.
- The connector normalizes the result.
- The historian stores it the same way as other protocols.

RTU is more sensitive to wiring and timing than TCP, so it is common to place an edge gateway in front of it.

## 7. MQTT And Sparkplug B Scenario

Use MQTT when sensors or gateways already publish telemetry.

### How to set it up

1. Set `MQTT_HOST` and `MQTT_PORT`.
2. Set the topic filter in `MQTT_TOPIC`.
3. Configure QoS if you need stronger delivery semantics.
4. Add TLS certificates if the broker requires them.
5. Set Last Will and Testament values if you want disconnect visibility.

### Sparkplug B

If the devices use Sparkplug B, the payload is more structured and industrially consistent.
The platform can still normalize it into the same event model.

### What happens in the platform

- MQTT messages are decoded.
- Invalid payloads go to the dead-letter path.
- Valid payloads become normalized events.
- Those events flow to Kafka and the historian.

MQTT is the best fit when the plant already has a broker or edge gateway.

## 8. REST Pull And HTTP Push

Choose **REST Pull** when an API exposes telemetry and the platform should poll
it. Enter the URL, GET or POST method, poll interval, timeout, optional auth
reference, response records path, and dotted field paths for source, asset, tag,
and value. Pagination and retries are bounded by the source configuration. The
connector creates deterministic canonical events and sends them through the
same Kafka, processor/Flink, historian, DLQ, and optional sink path as PLC
events.

Choose **HTTP Push** when a gateway or application already polls the source and
can send JSON to the platform. Save and enable the connection, then post to
`/api/v1/connections/<connection_id>/events` or the bounded `/events/batch`
endpoint. The endpoint accepts a single object or up to 1,000 objects, stamps
the connection and site identity, and deduplicates repeated event IDs or
`Idempotency-Key` values in the local process. Put authentication, rate limits,
and network exposure at the operator's reverse proxy or API security boundary.

## 9. Multiple PLCs And Sensors On One Line

This is the most common real plant setup.

Example:

- PLC A measures motor speed
- PLC B measures temperature
- vibration sensor gateway C measures vibration
- all three belong to the same production line

### How the platform handles it

- each source gets its own `source_id`
- each value maps to an asset and tag
- each event keeps its protocol identity
- the historian stores them separately
- the semantic layer can correlate them later through the shared asset model

### Do users need to configure this?

Yes, at least once.

They need to define:

- which source belongs to which site
- which line or area it belongs to
- which tags should be ingested
- which source IDs should stay separate

Without that mapping, the platform cannot know whether two readings belong to the same machine, the same line, or two unrelated devices.

## 10. Dashboard And Historian Behavior

When multiple sources are connected:

- the dashboard shows live state, alarms, trends, and pipeline status
- the historian stores the normalized copy for query and replay
- the UI can still show one production line as a single operational story while the data remains source-separated

The important rule is:

- streaming stays separated by source
- correlation happens in metadata, analytics, or semantic views

That is how you avoid mixing devices together too early.

## 11. What Apache Flink Does Here

Apache Flink is the high-throughput, stateful stream-processing option.

Use it when you want:

- keyed state per asset or device
- windowed calculations
- checkpointing and recovery
- higher-scale stream processing
- a production-grade alternative to the Python fallback

In this platform, the processor layer can run in Python for local development, but Flink is the direction for the larger hot path.

Flink does not replace the historian.

It sits between Kafka and the historian or AI outputs and is useful for:

- rolling metrics
- anomaly scoring
- enrichment
- event transformations
- replay-safe stateful processing

## 12. Practical First Install Flow

1. Start the platform runtime.
2. Bring up Kafka, the historian, and the API.
3. Choose one protocol first, usually OPC UA or Modbus TCP.
4. Configure one PLC or gateway.
5. Verify that a single source writes correctly to Kafka and the historian.
6. Add the second device.
7. Confirm the platform keeps the sources separate.
8. Add dashboards and alerts after the data is stable.

## 13. What To Do If You Do Not Have Real PLCs Yet

Use the built-in simulators and replay packs first.

Good starting cases:

- OPC UA simulator
- Modbus simulator
- MQTT publisher
- mixed industrial replay CSVs

That lets you validate:

- ingest
- normalization
- historian writes
- dashboard updates
- error handling
- reconnect behavior

## 14. Final Rule

Do not try to force every PLC or sensor into one universal configuration shape.

Instead:

- keep the protocol-specific details in the connector
- keep the source identity separate
- keep the historian as the durable record
- keep the semantic layer for later correlation

That is the safest way to scale from one machine to many machines and from one line to a whole site.

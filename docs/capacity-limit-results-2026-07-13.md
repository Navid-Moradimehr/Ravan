# Capacity Limit Results: Single Docker Node

## Scope

This campaign increased the number of run-qualified sites, simulated devices,
and aggregate event rate against the existing Docker Compose deployment. Each
generator published canonical events directly to Kafka topic
`industrial.normalized`. The campaign therefore measures the shared Kafka,
Flink, fanout, and TimescaleDB path, not the wire-level capacity of a specific
PLC protocol.

The tests were short capacity probes, not replacements for the validated
15-minute acceptance soaks. They intentionally stop at the first clear
backpressure boundary to avoid turning a development machine into an
uncontrolled resource-exhaustion test.

## Results

| Stage | Sites | Devices/site | Requested rate | Admitted rate | Producer failures | Final normalized-fanout lag | Result |
|---|---:|---:|---:|---:|---:|---:|---|
| A | 5 | 200 | 2,500 events/sec | ~2,499 events/sec | 0 | 0 | Passed |
| B | 10 | 500 | 10,000 events/sec | ~9,967 events/sec | 0 | 29,043 | Burst passed, lagged |
| C | 20 | 500 | 20,000 events/sec | ~15,969 events/sec | 0 | 133,231 | Capacity boundary |

Each stage ran for approximately 30 seconds. Stage B returned all consumer
lag to zero within about one minute after producers stopped. Stage C remained
replayable and continued draining, but it failed a zero-lag sustained-capacity
gate. The Stage C raw historian count was 479,073 events, below the requested
600,000 because the local generator processes and Docker stack could not
sustain the requested rate. No producer queue-full or delivery-failure events
were reported.

At the post-Stage C observation, Docker reported Kafka at about 237% CPU and
the Flink task manager at about 163% CPU on the local machine. Memory was not
the immediate constraint. Flink remained `RUNNING` with two tasks and its
checkpoint intervals increased materially under load. The first practical
limiting path is therefore the combined broker/Flink checkpoint/fanout and
historian write path, not the canonical event transformation itself.

## Capacity interpretation

For this machine and this Compose topology:

- approximately 2,500 events/sec sustained for the short probe was clean;
- approximately 10,000 events/sec is a burst level that creates recoverable
  downstream lag;
- approximately 16,000 admitted events/sec during the 20-site probe is beyond
  the zero-lag single-node operating envelope.

These are local engineering boundaries, not universal product limits. Event
size, partition count, database hardware, checkpoint interval, retention,
number of sinks, AI workload, and connector behavior all change the result.
For a production site, capacity planning should leave headroom and scale the
Kafka partitions, Flink task managers, and historian/fanout consumers before
the zero-lag boundary is reached.

## Protocol coverage

The 15-minute single-site and three-site soaks, and this capacity campaign,
used `services.ingestion.mock_generator`. It produced `source_protocol=mock`
events and published directly to Kafka. They did **not** open MQTT, OPC UA, or
Modbus connections.

The repository has separate Docker connector simulators and an edge-ingest
profile for MQTT, OPC UA, and Modbus TCP. The edge profile is configured with
`EDGE_PROTOCOLS=mqtt,opcua,modbus`, and the earlier industrial smoke campaign
used those simulated sources. That evidence validates the connector-to-
canonical-event boundary at smoke scale, but it is not equivalent to a
15-minute high-rate wire-protocol soak.

## What can be generalized

Once a connector successfully emits the canonical industrial event, the
downstream path is protocol-neutral. Kafka partitioning, Flink keyed state,
normalization, threshold evaluation, historian writes, replay, and dashboards
consume the canonical contract rather than MQTT/OPC UA/Modbus-specific
objects. This is why the capacity result is useful for the common processing
path.

It does not prove that every connector will work correctly in a real plant.
Protocol-specific risks remain: OPC UA subscriptions and status codes, MQTT
QoS/session behavior, Modbus register addressing and byte order, reconnects,
authentication, timestamps, quality flags, batching, and device-specific
mapping. REST, Sparkplug B, Modbus RTU, and OPC UA discovery are not covered by
these high-rate soaks.

## Recommended validation policy

Do not run a separate 15-minute capacity soak for every protocol. That would
duplicate the expensive downstream test. Instead keep a small mandatory
connector contract matrix:

1. One smoke test per enabled connector that connects, reads or receives a
   value, maps it to the canonical event, and verifies `source_protocol`, site,
   asset, tag, timestamp, unit, and quality.
2. One mixed MQTT + OPC UA + Modbus TCP run that verifies the shared Kafka and
   historian path with protocol labels preserved.
3. The existing high-rate Kafka capacity campaign for downstream scaling.
4. Protocol-specific reconnect and malformed-payload tests where the protocol
   has unique failure semantics.

This is the minimum evidence needed for an open-source release. Passing the
Kafka capacity test alone is not sufficient to claim universal PLC or sensor
compatibility.

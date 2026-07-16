# Live Industrial Simulation 2026-07-16

## Campaigns

Two real 15-minute wall-clock campaigns ran against the current Docker stack.
The source was the host mock generator publishing directly to
`industrial.normalized`. Flink remained the active processor; the Python
fallback was not used.

| Run | Producers | Attempted | Acknowledged | Failures | Queue full | Final normalized/processed/AI fan-out lag |
|---|---:|---:|---:|---:|---:|---:|
| `single-345a3007e700` | 1 x 100/s | 89,999 | 89,999 | 0 | 0 | 0 / 0 / 0 |
| `multi-cf3338b1058e` | 3 x 100/s | 270,000 | 270,000 | 0 | 0 | 0 / 0 / 0 |

Flink stayed `RUNNING` with two active tasks. TimescaleDB recorded exactly
270,000 `industrial_events` and 270,000 `processed_events` for the three
unique multisite IDs, 90,000 per site. The DLQ remained at zero. API, AI
gateway, Prometheus, Grafana, Kafka UI, and the core Docker services were
reachable after the run.

## Interpretation

This is a valid local end-to-end Kafka/Flink/historian soak, not a broker-free
benchmark. It does not exercise the native OPC UA, MQTT, or Modbus clients
because the generator enters at Kafka. Those connectors remain covered by the
separate protocol contract and simulator tests.

The default AI reporting policy was one hour with anomaly reporting disabled.
Consequently the 15-minute campaigns did not create new AI-enriched historian
rows. The AI gateway retained its Kafka offsets while accumulating bounded
evidence for the scheduled report, so its approximately 420k reported lag is
not equivalent to normalized or historian loss. An AI-specific soak requires a
temporary 600-second schedule or a sustained anomaly fixture.

## Evidence

- Single-site generator acknowledgement rate: `99.999 events/s`.
- Multisite acknowledgement rate: `99.999 events/s` per site.
- `industrial_events`: exact source accounting.
- `processed_events`: exact source accounting.
- DLQ: `0`.
- Final normalized, processed, and AI fan-out lag: `0`.

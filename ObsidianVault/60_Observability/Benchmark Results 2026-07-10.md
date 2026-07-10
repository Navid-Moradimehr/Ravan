# Benchmark Results 2026-07-10

The local simulator averaged **63,849 events/s** across six industrial-style
cases with zero invalid events. The mixed end-to-end pipeline processed
**27,498 events/s** using JSON and **34,955 events/s** using MessagePack.

MessagePack was **27.1% faster**, used **9.5% fewer serialized bytes**, and
reduced p99 latency from **0.0944 ms** to **0.0359 ms** in the same local run
shape. These numbers cover in-process validation, record building, keyed
state enrichment, and serialization. They do not measure a real PLC, Kafka
broker, TimescaleDB, network, or multi-site deployment.

Acceptance evidence:

- `503 passed, 4 warnings`
- Next.js production build passed
- Compose configuration passed
- Docker API, sink-route API, integrations UI, and edge metrics returned 200

The full report is in `docs/benchmark-results-2026-07-10.md`.

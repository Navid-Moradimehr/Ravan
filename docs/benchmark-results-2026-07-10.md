# Benchmark Results - 2026-07-10

## Scope

This pass validates the local deterministic processing and serialization
paths after the source-connection, Sparkplug B, store-and-forward, sink
routing, and notification-status changes. It does not claim PLC, Kafka,
TimescaleDB, network, or multi-site production capacity because those
external systems were not included in this run.

## Commands

```text
py -3.13 -m services.cli.datastreamctl benchmark real-world-simulator --events 5000 --batch-size 256 --warmup-events 500 --json
py -3.13 -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 5000 --batch-size 256 --warmup-events 500 --wire-format json --json
py -3.13 -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 5000 --batch-size 256 --warmup-events 500 --wire-format msgpack --json
```

## Results

| Test | Events | Invalid | Throughput | p50 | p95 | p99 | Payload |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Real-world simulator average | 30,000 across six cases | 0 | 63,849/s | n/a | n/a | n/a | n/a |
| End-to-end mixed, JSON | 5,000 | 0 | 27,498/s | 0.0286 ms | 0.0423 ms | 0.0944 ms | 3,121,547 B |
| End-to-end mixed, MessagePack | 5,000 | 0 | 34,955/s | 0.0219 ms | 0.0273 ms | 0.0359 ms | 2,824,676 B |

Compared with JSON in the same process and run shape, MessagePack was 27.1%
faster, reduced serialized bytes by 9.5%, and reduced p99 latency by 62.0%.
The result supports MessagePack as an optional internal wire format for
high-throughput paths; JSON remains the compatibility and debugging default.

## Interpretation

The results demonstrate deterministic local processing, not an industrial
deployment capacity guarantee. Kafka partitioning, broker durability,
TimescaleDB write throughput, connector polling rates, network latency, disk
spooling, and AI provider latency must be benchmarked in a site-specific
rehearsal. The recent changes are primarily reliability and deployment
configuration improvements, so no large throughput increase should be
expected from them.

## Verification status

- Python tests: `503 passed, 4 warnings`.
- UI production build: passed.
- Compose configuration: passed.
- Live Docker checks: API health, sink routes, integrations UI, and edge
  metrics returned HTTP 200.

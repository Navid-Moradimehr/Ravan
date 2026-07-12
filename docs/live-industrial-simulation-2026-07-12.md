# Live Industrial Simulation: 2026-07-12

## Test Type

This was a live Docker-backed simulation, not an in-process benchmark. The
platform services remained running while three simulated input paths produced
traffic:

- OPC UA: 3 simulated devices at 1 event/sec each
- MQTT: 8 simulated devices at 5 events/sec each
- Modbus: 4 simulated devices at 1 event/sec each

The campaign ran for 900 seconds and included warmup, sustained traffic, a
10x burst, source reconnect, processor restart, recovery, and drain phases.
It was run with `--no-build` after the Docker stack had been prepared, so image
build time was not included in the measurement.

## Result

The platform stayed operational through the campaign:

- API health remained healthy.
- AI gateway health remained healthy.
- Flink `iot-anomaly-processor` remained `RUNNING`.
- The processor restart phase completed and the service recovered.
- No failure was recorded in the API or AI health checks.

The campaign did not pass the final acceptance gate because downstream Kafka
consumer lag did not drain:

| Phase | Configured rate | Consumer lag | Container memory |
|---|---:|---:|---:|
| Warmup | 47 events/sec | 0 | 7,244 MB |
| Sustained | 47 events/sec | 0 | 7,191 MB |
| Burst | 470 events/sec | 26,680 | 7,428 MB |
| Reconnect | 47 events/sec | 40,335 | 7,465 MB |
| Restart | 47 events/sec | 9,079 | 7,506 MB |
| Recovery | 47 events/sec | 24,398 | 7,490 MB |
| Drain | 0 events/sec | 26,391 | 7,519 MB |

The final result was `passed=false` because lag increased from `9` to
`26,391`. The burst exposed a real capacity mismatch between ingestion and
downstream processing/historian consumers. A 120-second drain period was not
enough to recover the backlog.

## Interpretation

This is not evidence that the platform loses all data. It shows that the
current local stack can ingest traffic faster than the downstream pipeline can
process it during a burst. The next performance work should measure and tune
Kafka partitions, consumer parallelism, batch sizes, Flink task slots, historian
write batching, and backpressure before claiming burst-grade production
capacity.

The runner's aggregate simulator and edge counters were not identical because
simulator containers are recreated between phases and other protocol simulator
traffic can remain active. Therefore the reliable acceptance signal in this run
is consumer lag, service health, restart recovery, and the phase behavior, not
the raw generated-versus-edge counter difference.

## Docker State After Run

The dashboard image was rebuilt after the run to include the Historical Trend
time-span selector. The Historian route returned HTTP `200`; processor, Flink,
API, edge ingest, and dashboard containers were running afterward.

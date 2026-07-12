# Live Industrial Simulation 2026-07-12

This was a real Docker-backed 15-minute simulation, unlike the earlier
multi-site contract benchmark. It exercised three simulated inputs and the
running Kafka, edge ingest, processor, historian/fanout, Prometheus, and Flink
stack. The phases included warmup, sustained load, a 10x burst, reconnect,
processor restart, recovery, and drain.

The services remained healthy and Flink stayed RUNNING. The test failed its
final acceptance gate because consumer lag rose from 9 to 26,391 messages. Lag
was 0 during warmup and sustained traffic, rose to 26,680 during the burst,
peaked at 40,335 during reconnect, and did not drain within 120 seconds.
Container memory increased from approximately 7,068 MB at the initial snapshot
to 7,519 MB at the final snapshot.

This is a meaningful real-system finding: the local downstream pipeline cannot
yet absorb and drain the configured burst rate. It is not a data-loss proof,
but it prevents a claim of burst-grade production capacity. Future tuning
should focus on Kafka partitions/consumer parallelism, Flink slots, batching,
and historian write throughput.

The dashboard image was rebuilt after the run and the new Historical Trend
time-span selector is present in Docker.

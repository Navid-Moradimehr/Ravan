# Multi-Site Failure Benchmark

`datastreamctl benchmark multi-site-failure` simulates multiple independent
sites continuing local writes while central delivery is unavailable. It then
replays the queued events and verifies central count recovery and duplicate-free
identity handling.

The benchmark is a deterministic correctness test. It deliberately does not
claim Kafka, network, or S3 throughput.

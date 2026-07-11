# World-Model Data Foundation Benchmarks - 2026-07-11

These results are local mock/simulation measurements. They validate behavior
and relative regressions, not customer-site capacity.

## Application benchmarks

| Workload | Result |
|---|---:|
| Real-world simulator average, 6 cases, 10,000 events each | 69,213.29 events/sec |
| Mock normal | 68,108.01 events/sec |
| Mock drift | 70,685.62 events/sec |
| Mock spike | 75,248.68 events/sec |
| Simulated SWaT-shaped line | 73,016.95 events/sec |
| Mixed industrial benchmark | 65,307.49 events/sec |
| Multi-site correlation | 62,912.98 events/sec |
| CGR-style stream slice | 36,805.99 events/sec |
| CGR-style p99 latency | 0.0545 ms |
| Metadata-plane snapshots | 28.68 snapshots/sec |
| Semantic graph queries | 8,243.16 queries/sec |
| Training bundle compilation | 9,998.06 records/sec |
| Operational event envelope serialization | 89,145.63 events/sec |

## Docker workload benchmarks

| Workload | Result |
|---|---:|
| Kafka producer, 512-byte records, acks=all, 10,000 records | 17,482.5 records/sec, 8.54 MB/sec |
| Kafka producer average latency | 152.15 ms |
| Kafka producer p99 latency | 202 ms |
| Kafka consumer, 10,000 records | 27,548.21 records/sec |
| Iceberg/MinIO normalized append, 1,000 rows | 1,460.19 rows/sec |
| Iceberg/MinIO table scan | 67,546.32 rows/sec |

The Kafka numbers are broker-only and should not be compared directly with
application pipeline throughput. The Iceberg write number includes catalog
commit and object-storage work on a single local Docker deployment; batch size,
object-store latency, file sizing, and catalog placement will dominate real
deployments.

## External benchmark references

- TSBS is suitable for deterministic time-series bulk-load and query testing;
  its IoT workload includes missing, empty, and out-of-order entries.
- TPCx-IoT is a formal gateway benchmark for large device-ingestion systems,
  but its certification and workload scale are not reproducible on this local
  development machine.
- Apache Kafka provides producer and consumer performance tools, used for the
  broker-only measurements above.
- Apache Iceberg publishes Spark/Parquet read and write benchmarks. Those are
  useful after adding Spark or another analytical query engine, not as a
  replacement for this platform's sink benchmark.

## Interpretation

The new features are mock-benchmarkable and have basic measured coverage.
What remains unmeasured is external S3 latency, catalog contention, multi-node
Kafka replication, concurrent historian reads/writes, and target industrial
network behavior. Those require deployment-owned infrastructure.

# World Model Benchmark Results 2026-07-11

Local simulated results:

- application simulator average: 69,213.29 events/sec
- CGR-style stream slice: 36,805.99 events/sec
- CGR-style p99: 0.0545 ms
- Kafka producer: 17,482.5 records/sec at 512 bytes
- Kafka consumer: 27,548.21 records/sec
- Iceberg/MinIO append: 1,460.19 rows/sec for a 1,000-row batch
- Iceberg/MinIO scan: 67,546.32 rows/sec
- training bundle compiler: 9,998.06 records/sec

These are local mock measurements. External S3, catalog contention, replicated
Kafka, concurrent Timescale reads/writes, and target-site network behavior
remain deployment-owned validation.

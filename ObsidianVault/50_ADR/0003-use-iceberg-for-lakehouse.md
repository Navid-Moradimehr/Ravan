# ADR 0003: Use Iceberg for the Lakehouse

## Status

Accepted

## Context

The target architecture needs a long-term analytical store alongside the
TimescaleDB historian (operational, short-window queries). The lakehouse must
serve AI training, replay, and batch analytics, and it should map cleanly to the
open-source release where users bring their own object storage.

Candidates were Apache Iceberg and Delta Lake.

## Decision

Use Apache Iceberg backed by MinIO (S3-compatible object storage), accessed
through `pyiceberg` and `pyarrow` from the Python sink layer.

## Rationale

- Iceberg has a stronger Flink connector and first-class support across Flink,
  Spark, and Trino, which aligns with the platform's Flink runtime path.
- `pyiceberg` gives a pure-Python write path that integrates with the sink
  abstraction without a separate compute engine.
- MinIO is already part of the stack (S3-compatible), so the lakehouse reuses
  the object-storage layer instead of introducing a new dependency.
- Iceberg's open table format avoids vendor lock-in for an open-source release.

## Consequences

- The lakehouse sink is optional (`SINKS=lakehouse`); without it the platform
  still runs with the historian and Kafka sinks.
- `pyiceberg` and `pyarrow` are added to `requirements.txt`.
- Users can swap the catalog (REST, Hive, Glue) or storage (S3, GCS, ADLS) via
  environment variables without changing the sink code.

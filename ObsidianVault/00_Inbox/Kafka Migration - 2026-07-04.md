# Kafka Migration - 2026-07-04

## Completed

- Replaced Redpanda compose service with Kafka KRaft.
- Replaced Redpanda Console references with Kafka UI.
- Switched broker env resolution to `KAFKA_BROKERS` only.
- Updated the landing page into a routed command center plus dedicated pipeline, processing, historian, observability, and integrations pages.
- Updated the main runbook and acceptance/test guidance to match the Kafka stack.
- Added a full historian schema for `industrial_events`, `processed_events`, `ai_enriched`, and `dead_letter_events`.
- Created the missing industrial Kafka topics: `industrial.raw`, `industrial.normalized`, and `industrial.dlq`.
- Rebuilt the API service against the shared requirements file so auth/runtime imports resolve correctly.

## Still to validate

- Refresh benchmark numbers against the previous broker baseline.
- Resolve the local desktop port conflict on `3006` if the dashboard container itself needs to run on that port.

## Notes

- The app keeps schema validation in application code; an external schema registry is not required for the current JSON-first flow.
- Host-side scripts should still default to the external broker port, while containers use `kafka:9092`.
- The live stack currently validates cleanly with Kafka, TimescaleDB, Flink, Debezium, and the split UI routes.

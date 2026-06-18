# ADR 0001: Use Redpanda, PyFlink, and FastAPI

## Status

Accepted

## Decision

Use Redpanda for Kafka-compatible local streaming, PyFlink for stateful stream processing, and FastAPI for the AI gateway.

## Consequences

- Keeps the MVP Python-oriented.
- Avoids running both Flink and ksqlDB in the first slice.
- Leaves room for BI/dashboard features without coupling them to the broker.

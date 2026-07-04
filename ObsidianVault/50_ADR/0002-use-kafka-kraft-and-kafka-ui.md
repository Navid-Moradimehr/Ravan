# ADR 0002: Use Kafka KRaft and Kafka UI

## Status

Accepted

## Context

The platform started with Redpanda because it simplified local development, but the open-source release needs a broker stack that maps cleanly to standard Kafka deployments and avoids Redpanda-specific operational coupling.

## Decision

Use Kafka in KRaft mode for the broker layer and Kafka UI for broker inspection. Keep schema validation in application code instead of depending on a broker-bundled registry.

## Consequences

- Broker behavior aligns with standard Kafka deployments.
- The dev stack is easier to compare with industrial Kafka-based environments.
- The app can still run without an external schema registry because it already validates and normalizes events in application code.

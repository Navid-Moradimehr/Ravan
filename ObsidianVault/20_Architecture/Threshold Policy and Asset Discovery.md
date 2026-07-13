# Threshold Policy and Asset Discovery

## Status

- Asset/tag catalog: implemented as a logical metadata boundary.
- Observed catalog updates: implemented on successful historian fan-out.
- Threshold policy table and API: implemented.
- Threshold policy outbox + compacted Kafka distribution: implemented.
- Sync status route for UI and operator visibility: implemented.
- Operator policy editor: implemented on Integrations.
- Full historical catalog reconciliation: implemented as a bounded operator API.
- Distributed alarm lifecycle state in Flink keyed state: implemented with
  checkpointed value state.
- External limit import: implemented through the Integrations JSON importer.
- Single-node Flink capacity default: Compose uses parallelism 1; distributed
  deployments must size slots before increasing it.

## Local verification

Use `docker compose -f docker/docker-compose.yml up -d --build`, open
`http://localhost:3006/integrations`, and use the **Alarm and threshold
policies** panel. Verify the distributed runtime at
`http://localhost:18088/jobs/overview`; the `iot-anomaly-processor` job should
be `RUNNING`. The runtime image supplies PyFlink's classpath, Python worker,
Beam/grpc dependencies, and checkpoint-compatible worker state.

## Connections

```text
registry / PLC limits / operator edit
              |
              v
       metadata policy store
              |
              +--> outbox relay --> compacted Kafka policy topic
              |
normalized event -> Python/Flink runtime -> processed_events
                         |
                         +-> threshold provenance and final severity
                         |
                         +-> policy snapshot cache
```

The registry remains the default source. Explicit operator policies override
defaults. Observed signals extend discovery but do not silently become mapped
engineering assets. The historian stores measurements and decisions; metadata
stores what the limits and signal identities are.

## Architectural guardrails

- Do not add Spark to asset dropdown requests.
- Do not make the dashboard infer a company topology from arbitrary telemetry.
- Do not treat a threshold policy as a PLC safety interlock.
- Do not claim Flink alarm continuity until its keyed state owns deadband and
  delay transitions across workers.
- Keep the policy store optional for deployments that only need ingestion and
  historian writes.
- If Kafka is unavailable, the policy save should remain durable in the
  historian outbox and surface a pending sync state instead of failing the
  operator workflow.

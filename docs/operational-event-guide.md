# Operational Event Guide

Telemetry describes what equipment measured. The `industrial.operational`
topic describes the context needed to interpret those measurements: actions,
outcomes, maintenance records, operator annotations, context changes, and
episode boundaries.

The platform provides the envelope and Kafka durability. Users provide the
meaning and adapters for their MES, ERP, CMMS, PLC audit log, SCADA, or
operator system.

## Event Shape

```json
{
  "event_type": "control.command.applied",
  "event_kind": "action",
  "source_id": "plc-audit",
  "site_id": "plant-a",
  "entity_id": "pump-01",
  "occurred_at": "2026-07-11T10:00:00Z",
  "correlation_id": "batch-42",
  "causation_id": "operator-request-8",
  "payload": {
    "command": "speed_setpoint",
    "requested": 42,
    "applied": 40,
    "mode": "manual"
  }
}
```

`payload` is intentionally extensible. A utilities company can send breaker
operations, a water plant can send valve actions, and a factory can send
recipe or batch transitions without changing the platform event model.

## API Path

POST the event to `/api/v1/operational/events`. The API validates the common
envelope and publishes it to Kafka. It does not write directly to the
historian. This keeps action/outcome ingestion replayable and avoids coupling
the API to a particular company database.

## Archive Path

Kafka is the durable operational-event boundary. With the extended lakehouse
profile and `OPERATIONAL_SINKS=lakehouse`, the optional operational fan-out
archives events in a separate Iceberg table with `event_stage=operational`.
If the archive is unavailable, Kafka retains the event for later recovery.

The semantic graph remains a queryable projection for selected actions,
states, and relationships. It is not intended to be the high-volume action
log.

## Training Use

Actions, outcomes, and boundaries are required for control-oriented datasets.
The platform does not infer rewards, safety limits, or episode definitions.
Users must map their domain records into this contract and declare how those
records align with telemetry in a training dataset manifest.

# Schema Governance

> Competitive inspiration 1 (pillar 10 - schema registry safe evolution).
> Added 2026-07-06.

## Context

The platform validates event schemas in application code (ADR 0002) via an
in-memory `SchemaRegistry` in `services/common/schema_registry.py`. Until now
the registry stored versions but did **not** enforce evolution rules, so a
breaking schema change could be registered silently and break downstream
consumers (fan-out, historian sink, lakehouse sink).

## Decision

Add standard compatibility-mode enforcement on `register()`:

- `BACKWARD` (default) - new schema can read data written with the previous
  version. Blocks: removing a required field, changing a field type, making an
  optional field required. Allows: adding an optional field.
- `FORWARD` - previous schema can read data written with the new version.
  Blocks: adding a required field.
- `FULL` - both backward and forward.
- `NONE` - no enforcement (internal bootstrap / forced migrations only).

`IncompatibleSchemaError` is raised on violation. `enforce=False` bypasses the
check (used for the built-in v1 bootstrap). Per-schema mode via
`set_compatibility`; per-call override via the `compatibility` kwarg.

## Persistence

The registry remains an in-process platform component, but it can now be given
an optional file path through `SCHEMA_REGISTRY_PATH` so the schema/version
history survives restarts in single-node or Docker Compose deployments.

This is intentionally lightweight:

- no new metadata database
- no separate registry service
- no change to the default in-memory behavior when the path is unset

State is serialized as JSON and written atomically so release-gate artifacts and
local production installs see the same schema history after a restart.

## Data flow impact

```
edge/ingest -> industrial.raw -> processor(normalize+validate) -> industrial.normalized
                                                                        |
                          SchemaRegistry.validate() gates each stage <---+
                                                                        |
                                                        fan-out -> historian/lakehouse/kafka sinks
```

The registry governs `industrial_event`, `processed_event`, and `benchmark_event`.
A v2 of any of these that removes a required field or changes a type is now
rejected at registration time before it can reach a consumer.

## Why not an external registry

The platform's open-source stance is "validate in app code, no extra infra
required" (ADR 0002). This enforcement is pure Python and ships in-process, so
operators get safe evolution without deploying Confluent/Apicurio.

## Tests

`tests/test_schema_registry_compat.py` - 14 cases covering each mode, the
bypass flag, per-call override, mode validation, bootstrap behavior, and
optional persistence/reload behavior.

## Related

- [[50_ADR/0002-use-kafka-kraft-and-kafka-ui|ADR 0002]]
- [[20_Architecture/Sink Architecture]]
- `comparission.md` pillar 10

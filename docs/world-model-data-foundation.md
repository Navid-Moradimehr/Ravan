# World-Model Data Foundation Status

The platform now provides the infrastructure needed to collect the evidence
that future industrial world-model work can use, while keeping company-specific
meaning and model training outside the core runtime.

## Platform Core

- replayable canonical telemetry on Kafka
- TimescaleDB historian for operational reads
- optional Iceberg archive of normalized events over MinIO or external S3-compatible storage
- SQL-catalog local reference deployment and external REST-catalog option
- semantic entities, relationships, observations, states, actions, documents,
  and lineage primitives
- versioned source, mapping, schema, and event provenance identities
- `industrial.operational` events for actions, outcomes, boundaries, context,
  maintenance, and annotations
- versioned training manifests and portable dataset bundles

## User-Owned Configuration

Users must supply PLC/MES/ERP/CMMS adapters, plant topology truth, calibration
and PLC-program versions, action meaning, episode boundaries, reward/objective
definitions, safety constraints, retention, storage/IAM, and the training
framework/GPU environment.

The platform does not infer a reward from telemetry, automatically turn sensor
values into control actions, or connect a trained planner to a PLC.

## Readiness Boundary

Passive JEPA-style preparation can begin with synchronized normalized
observations and semantic context. Dreamer/MuZero preparation additionally
requires operational action events, outcomes, and episode boundaries. The
platform can transport and archive those records, but the company must map and
validate their process semantics.

See the lakehouse, operational-event, training-dataset, JEPA, Dreamer, and
MuZero guides for the complete setup path.

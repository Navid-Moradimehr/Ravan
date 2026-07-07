# Metadata Plane

The platform now has a logical metadata plane, not a new microservice.

## Purpose

The metadata plane is the single inspection surface for platform knowledge:

- schema registry
- prompt registry
- model registry
- dataset catalog
- retrieval catalog
- semantic core
- semantic store summaries
- lineage previews
- operational memory snapshot

It is intentionally read-only for now.

## Ownership Boundaries

Platform core owns:

- industrial event contracts
- Kafka contracts
- historian contracts
- replay contracts
- metadata contracts
- semantic primitives
- AI gateway contracts
- benchmark framework

Users own:

- industrial processes
- MES
- ERP
- plant topology
- secrets
- infrastructure
- GPU sizing
- retention policies
- company-specific ontologies

## Memory Layers

- Historical Memory: telemetry, alarms, historian writes, replayable measurements.
- Semantic Memory: assets, topology, ontology packs, relationships, lineage.
- Operational Memory: maintenance, operator actions, shifts, recipes, work orders, approvals, and incident history.

Operational Memory is documented now so future features can fit the same boundary, but it is still largely user-owned in the current release.

Operational memory now has a read-only snapshot surface over alerts, annotations, shifts, reports, and backups, but it does not yet own work orders or maintenance workflows.

## Current Implementation

- `services/common/metadata_plane.py`
- `services/api_service/routers/metadata.py`
- `services/common/operational_memory.py`
- `services/api_service/routers/operational_memory.py`
- `/api/v1/metadata`
- `/api/v1/metadata/operational`

The implementation aggregates existing registries and catalogs. It does not introduce a second persistence system.

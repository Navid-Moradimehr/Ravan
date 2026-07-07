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
- asset registry snapshot
- event catalog
- governance snapshot
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

Lineage is exposed twice on purpose:

- the metadata plane keeps lineage previews and counts as part of platform memory
- the dedicated `/api/v1/lineage` snapshot gives operators and integrations a normalized read-only lineage view without forcing them through the semantic write API

Asset metadata is exposed twice as well:

- the metadata plane keeps the current asset hierarchy as platform knowledge
- the dedicated `/api/v1/metadata/assets` snapshot gives operators a flattened registry view for validation and rollout checks

Governance is also exposed as a lightweight lifecycle snapshot:

- the metadata plane keeps schema, model, prompt, and dataset registries together
- the dedicated `/api/v1/metadata/governance` snapshot summarizes readiness and validation issues without turning the platform into a workflow engine

## Current Implementation

- `services/common/metadata_plane.py`
- `services/api_service/routers/metadata.py`
- `services/common/operational_memory.py`
- `services/api_service/routers/operational_memory.py`
- `services/common/lineage_contract.py`
- `services/api_service/routers/lineage.py`
- `services/common/asset_registry.py`
- `services/api_service/routers/asset_registry.py`
- `services/common/event_catalog.py`
- `services/api_service/routers/event_catalog.py`
- `services/common/governance_plane.py`
- `services/api_service/routers/governance.py`
- `/api/v1/metadata`
- `/api/v1/metadata/operational`
- `/api/v1/metadata/assets`
- `/api/v1/metadata/events`
- `/api/v1/metadata/governance`
- `/api/v1/lineage`

The implementation aggregates existing registries and catalogs. It does not introduce a second persistence system.

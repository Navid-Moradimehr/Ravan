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
- dataset-builder contract

It is intentionally read-only for now.

## Logical Planes

- Data Plane: ingestion, Kafka, processing, historian writes, and optional lakehouse sinks.
- Control Plane: metadata, schema registry, lineage, event catalog, governance, and dataset-builder contracts.
- Intelligence Plane: AI gateway, retrieval, semantic layer, and versioned AI outputs.

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
The underlying alert, annotation, and report-template stores can be made file-backed for durable local installs, so the snapshot reflects restart-safe operator state without adding an operational workflow engine.
Report schedules are stored with the persisted template metadata and rehydrated when scheduling support is available, so the release story can keep recurring exports without promoting the feature into a workflow engine.

Lineage is exposed twice on purpose:

- the metadata plane keeps lineage previews and counts as part of platform memory
- the dedicated `/api/v1/lineage` snapshot gives operators and integrations a normalized read-only lineage view without forcing them through the semantic write API

Asset metadata is exposed twice as well:

- the metadata plane keeps the current asset hierarchy as platform knowledge
- the dedicated `/api/v1/metadata/assets` snapshot gives operators a flattened registry view for validation and rollout checks
- the external asset CRUD surface now has optional file-backed state via `ASSET_STORE_PATH` or `ASSET_REGISTRY_PATH`, so user edits persist across restarts in single-node installs without turning the asset store into a new service

Governance is also exposed as a lightweight lifecycle snapshot:

- the metadata plane keeps schema, model, prompt, and dataset registries together
- the dedicated `/api/v1/metadata/governance` snapshot summarizes readiness and validation issues without turning the platform into a workflow engine
- the agent-governance section inside that snapshot keeps diagnostic tools read-only and supervised actions approval-gated

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
- `services/common/metadata_artifacts.py`
- `services/common/dataset_builder.py`
- `/api/v1/metadata`
- `/api/v1/metadata/operational`
- `/api/v1/metadata/assets`
- `/api/v1/metadata/events`
- `/api/v1/metadata/governance`
- `/api/v1/lineage`
- `data/metadata/*.json` report artifacts written by release-gate and rollout-acceptance commands

The logical metadata plane can be persisted as JSON artifacts for release gates and benchmark archives, but it still does not become a separate service or database.
The schema registry now also has optional file-backed state via `SCHEMA_REGISTRY_PATH`, so compatibility history can survive process restarts without adding a new metadata service.
The model registry and prompt registry now also support optional file-backed state through `MODEL_REGISTRY_PATH` and `PROMPT_REGISTRY_PATH`, which keeps AI role bindings and prompt templates durable in single-node and Docker Compose installs.
The dataset catalog now also supports optional file-backed state through `DATASET_CATALOG_PATH`, so benchmark and release-candidate dataset listings can remain stable across restarts without becoming a separate data-service boundary.
The dataset-builder contract is still logical only; it describes how curated, versioned datasets should be created for AI, benchmarking, and replay without exposing raw historian data directly.
The implementation aggregates existing registries and catalogs. It does not introduce a second persistence system.

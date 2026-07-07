# Platform Semantic Core

The platform now exposes a universal semantic substrate alongside the existing industrial asset model.

## What Was Added

- Platform primitives: entity, relationship, event, observation, measurement, state, action, document, location, policy, time, workflow, schema, lineage.
- Ontology packs: a stable platform-core pack plus a manufacturing pack that preserves the current app vocabulary.
- Semantic projection: the current `Site -> Area -> Line -> Cell -> Asset -> Tag` hierarchy can now be projected into a graph without changing the source model.
- API surface: `/api/v1/semantic/core` and `/api/v1/semantic/graph`.
- Dedicated lineage snapshot: `/api/v1/lineage` exposes a read-only OpenLineage-style view over the semantic lineage store.
- Graph query surface: `/api/v1/semantic/graph/search`, `/api/v1/semantic/graph/entities/{entity_id}`, and `/api/v1/semantic/graph/relationships/{relationship_id}`.
- Persistent store: the semantic graph now persists to Postgres/Timescale when available, with `data/semantic/semantic-store.json` kept as an offline fallback for tests and local development.
- Write surface: ontology packs, entities, relationships, documents, workflows, observations, and lineage can be created through the semantic API.
- Benchmark: a semantic-graph projection benchmark that measures projection cost separately from ingestion and historian paths.
- Benchmark: a semantic-graph query benchmark that measures graph-search throughput separately from projection.
- Benchmark: a semantic-store write benchmark that measures persistence throughput separately from read/query paths.
- Retrieval and modeling context now include semantic-graph documents and ontology-pack context so the AI layer can consume the ontology directly.
- Logical metadata plane: schema registry, model registry, prompt registry, dataset catalog, retrieval catalog, and semantic-store summaries are exposed through one inspection surface without adding a new microservice.
- The metadata plane now includes lineage previews, while the dedicated lineage endpoint provides a normalized snapshot for operators and downstream tooling.
- The metadata plane also now includes the asset registry snapshot and canonical event catalog so rollout validation can inspect both configured assets and Kafka contracts from one place.
- The metadata plane now exposes a lightweight governance snapshot for schema/model/prompt lifecycle without introducing a workflow engine.
- Operational memory snapshot: alerts, annotations, OEE shifts, reports, and backup readiness are exposed as a logical operator-state surface without turning the platform into a MES.

## Design Rule

Manufacturing concepts stay as a domain pack. The platform core only owns universal primitives and cross-domain relationships.
Metadata is separate from historian data. Historian answers what happened, metadata answers what exists and how it is governed, and the semantic layer answers how things are related.
Operational memory is separate again: it answers what the operator is dealing with right now, but still stays read-only and lightweight in the current release.

## Current Status

- Existing industrial functionality remains intact.
- The digital twin is still a projection layer, not the semantic source of truth.
- The semantic graph is the first step toward a knowledge-graph backbone for future AI, simulation, and reasoning workloads.

# Platform Semantic Core

The platform now exposes a universal semantic substrate alongside the existing industrial asset model.

## What Was Added

- Platform primitives: entity, relationship, event, observation, measurement, state, action, document, location, policy, time, workflow, schema, lineage.
- Ontology packs: a stable platform-core pack plus a manufacturing pack that preserves the current app vocabulary.
- Semantic projection: the current `Site -> Area -> Line -> Cell -> Asset -> Tag` hierarchy can now be projected into a graph without changing the source model.
- API surface: `/api/v1/semantic/core` and `/api/v1/semantic/graph`.
- Graph query surface: `/api/v1/semantic/graph/search`, `/api/v1/semantic/graph/entities/{entity_id}`, and `/api/v1/semantic/graph/relationships/{relationship_id}`.
- Persistent store: the semantic graph now persists to Postgres/Timescale when available, with `data/semantic/semantic-store.json` kept as an offline fallback for tests and local development.
- Write surface: ontology packs, entities, relationships, documents, workflows, observations, and lineage can be created through the semantic API.
- Benchmark: a semantic-graph projection benchmark that measures projection cost separately from ingestion and historian paths.
- Benchmark: a semantic-graph query benchmark that measures graph-search throughput separately from projection.
- Benchmark: a semantic-store write benchmark that measures persistence throughput separately from read/query paths.
- Retrieval and modeling context now include semantic-graph documents and ontology-pack context so the AI layer can consume the ontology directly.

## Design Rule

Manufacturing concepts stay as a domain pack. The platform core only owns universal primitives and cross-domain relationships.

## Current Status

- Existing industrial functionality remains intact.
- The digital twin is still a projection layer, not the semantic source of truth.
- The semantic graph is the first step toward a knowledge-graph backbone for future AI, simulation, and reasoning workloads.

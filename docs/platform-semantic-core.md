# Platform Semantic Core

The platform now exposes a universal semantic substrate alongside the existing industrial asset model.

## What Was Added

- Platform primitives: entity, relationship, event, observation, measurement, state, action, document, location, policy, time, workflow, schema, lineage.
- Ontology packs: a stable platform-core pack plus a manufacturing pack that preserves the current app vocabulary.
- Semantic projection: the current `Site -> Area -> Line -> Cell -> Asset -> Tag` hierarchy can now be projected into a graph without changing the source model.
- API surface: `/api/v1/semantic/core` and `/api/v1/semantic/graph`.
- Graph query surface: `/api/v1/semantic/graph/search`, `/api/v1/semantic/graph/entities/{entity_id}`, and `/api/v1/semantic/graph/relationships/{relationship_id}`.
- Benchmark: a semantic-graph projection benchmark that measures projection cost separately from ingestion and historian paths.
- Benchmark: a semantic-graph query benchmark that measures graph-search throughput separately from projection.

## Design Rule

Manufacturing concepts stay as a domain pack. The platform core only owns universal primitives and cross-domain relationships.

## Current Status

- Existing industrial functionality remains intact.
- The digital twin is still a projection layer, not the semantic source of truth.
- The semantic graph is the first step toward a knowledge-graph backbone for future AI, simulation, and reasoning workloads.

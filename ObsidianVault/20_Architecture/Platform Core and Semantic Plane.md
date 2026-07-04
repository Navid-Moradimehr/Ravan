# Platform Core and Semantic Plane

## Goal

Keep the current industrial app intact, but project it onto a universal semantic core that can support future AI, world models, and digital twins.

## Added In Code

- Universal primitives: entity, relationship, event, observation, measurement, state, action, document, location, policy, time, workflow, schema, lineage.
- Ontology packs: `platform.core` and `industry.manufacturing`.
- Semantic graph projection from the current asset hierarchy.
- API endpoints:
  - `/api/v1/semantic/core`
  - `/api/v1/semantic/graph`
- Graph query endpoints:
  - `/api/v1/semantic/graph/search`
  - `/api/v1/semantic/graph/entities/{entity_id}`
  - `/api/v1/semantic/graph/relationships/{relationship_id}`
- Write and persistence:
  - Postgres-backed semantic store with file fallback at `data/semantic/semantic-store.json`
  - write endpoints for ontology packs, entities, relationships, documents, workflows, observations, and lineage
- Benchmark:
  - semantic graph projection slice
  - semantic graph query slice
  - semantic store write slice
- AI context:
  - semantic graph entities, relationships, and ontology packs are now included in retrieval/modeling context packages
- Benchmark realism:
  - benchmark tests now use the mixed industrial CSV fixture and protocol-shaped simulator cases instead of tiny hand-written samples

## Architecture Note

The manufacturing model stays as a domain pack. The platform core should remain generic enough to support other industries without changing code.

## Current Interpretation

- The asset hierarchy is still useful for UI and operations.
- The knowledge graph should become the semantic backbone over time.
- The digital twin should stay a projection, not the source of truth.
- Lineage should be recorded at ingest time and when semantic writes happen so AI and simulation can later reconstruct provenance.
- The semantic plane should default to the database backend when the historian is available and fall back to file-backed mode only for offline development.
- Benchmark tests should validate the real industrial-shaped flows the platform is expected to handle, even when those flows are still simulated locally.

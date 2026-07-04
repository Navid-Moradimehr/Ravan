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
- Benchmark:
  - semantic graph projection slice

## Architecture Note

The manufacturing model stays as a domain pack. The platform core should remain generic enough to support other industries without changing code.

## Current Interpretation

- The asset hierarchy is still useful for UI and operations.
- The knowledge graph should become the semantic backbone over time.
- The digital twin should stay a projection, not the source of truth.

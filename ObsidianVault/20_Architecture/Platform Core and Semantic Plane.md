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
- Metadata plane:
  - schema registry, model registry, prompt registry, dataset catalog, retrieval catalog, and semantic-store summaries are exposed through one logical inspection surface
  - metadata is treated as platform memory, separate from historian telemetry and separate from the semantic graph
  - the schema registry now has optional file-backed state for local and release-gate deployments, but it still remains an in-process platform boundary rather than a separate service
  - the model registry and prompt registry also support optional file-backed state for durable single-node installs, without changing their in-process ownership boundary
- Lineage:
  - a dedicated read-only `/api/v1/lineage` snapshot exposes an OpenLineage-style view over semantic lineage without moving ownership out of the semantic plane
- Asset registry and event catalog:
  - the asset hierarchy now has a flattened registry snapshot for rollout validation
  - the canonical Kafka topic contract is exposed as a read-only event catalog for operators and tooling
- Governance snapshot:
  - schema, model, prompt, and dataset registries are summarized in a lifecycle view
  - promotion workflow remains out of scope until the platform has a real governance engine
- Metadata artifacts:
  - release-gate and rollout-acceptance now persist the logical metadata plane and governance snapshots as JSON report artifacts
  - a benchmark exists for snapshot construction so metadata overhead stays visible
- Operational memory:
  - alerts, annotations, OEE shifts, report inventory, and backup readiness are exposed through one read-only operator-state surface
  - work orders, approvals, and maintenance plans remain user-owned until a later phase
- Benchmark realism:
  - benchmark tests now use the mixed industrial CSV fixture and protocol-shaped simulator cases instead of tiny hand-written samples
- Distributed rollout:
  - plant-local and federated site profiles now export `SEMANTIC_STORE_BACKEND=db` so the semantic plane is explicitly database-backed in distributed installs
  - the simulator now includes a dedicated `multi-site-correlation` case for correlated PLC signals across sites

## Architecture Note

The manufacturing model stays as a domain pack. The platform core should remain generic enough to support other industries without changing code.

## Current Interpretation

- The asset hierarchy is still useful for UI and operations.
- The knowledge graph should become the semantic backbone over time.
- The digital twin should stay a projection, not the source of truth.
- Lineage should be recorded at ingest time and when semantic writes happen so AI and simulation can later reconstruct provenance.
- The semantic plane should default to the database backend when the historian is available and fall back to file-backed mode only for offline development.
- The schema registry should stay lightweight and in-process, but optional file-backed state is useful for durable single-node installs and repeatable release artifacts.
- The model registry and prompt registry should stay lightweight and in-process, but optional file-backed state is useful for durable single-node installs and repeatable release artifacts.
- Benchmark tests should validate the real industrial-shaped flows the platform is expected to handle, even when those flows are still simulated locally.
- Multi-site correlation should be benchmarked as its own workload shape because it stresses both isolation and cross-site reasoning.
- The dedicated lineage snapshot is an operator-facing projection, not a second lineage store.
- The asset registry snapshot is a projection of the existing hierarchy, not a second source of truth for plant topology.
- The event catalog is a contract view, not a substitute for the project manifest.
- The governance snapshot is a lifecycle summary, not a new workflow system.
- The metadata artifact bundle is an archive format, not a new storage engine.

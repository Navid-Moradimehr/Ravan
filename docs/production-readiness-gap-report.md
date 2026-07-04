# Production Readiness Gap Report

**Date**: 2026-07-04

This report summarizes the current state of the platform after the semantic-plane hardening, industrial benchmark fixture updates, and multi-site correlation work.

## 1. What Is Done

### Core runtime

- Multi-protocol ingest, normalization, replay, and historian write paths are present.
- Kafka-backed runtime wiring exists for the streaming path.
- Flink-local and Flink-production contracts are present, with a Python fallback for local development.
- Site separation is explicit through `site_id`, `source_id`, `source_protocol`, `asset_id`, and `tag`.
- API routing is split into focused modules.
- WebSocket/live update paths exist.
- The edge ingest and processor hot paths are already decomposed into smaller units.

### Semantic and AI foundations

- Universal semantic primitives exist.
- Ontology packs exist for the platform core and the manufacturing domain.
- The semantic graph is now persisted in Postgres/Timescale when available, with file fallback for offline development.
- Retrieval and modeling context packages now include semantic graph context.
- Read-only agent tooling exists.
- Open-weight and OpenAI-compatible model integration exists as a provider-neutral abstraction.

### Multi-site and rollout foundations

- Site profiles exist for `single-site`, `plant-local`, and `federated`.
- The project manifest carries sites, source inventory, bridge rules, and correlation groups.
- Site-profile validation exists.
- Release-gate and rollout-acceptance commands exist.
- Backup and restore tooling exists.
- Helm and systemd export paths exist.

### Benchmarking and validation

- Mixed industrial benchmark data exists in the repo.
- Real-world simulator cases cover:
  - `mock-normal`
  - `mock-drift`
  - `mock-spike`
  - `multi-plc-line`
  - `burst-load`
  - `dropout-reconnect`
  - `multi-site-correlation`
  - `industrial-benchmark`
- Site-profile matrix and calibration benchmarks exist.
- CGR gap reporting exists.
- Benchmarks now use industrial-shaped fixtures rather than tiny hand-written samples.

## 2. What Is Still Missing

### Hard production gaps

- Real target-site validation on actual broker, historian, and cluster topology.
- Multi-node Kubernetes pilot validation.
- Restore and rollback drill measurements on two or more real site profiles.
- Real PLC and sensor traffic validation against vendor devices.
- Broader vendor compatibility validation across more edge protocols and device families.

### Operational maturity gaps

- Model evaluation and promotion lifecycle.
- Diagnostic-agent runtime with read-only tools.
- Supervised action-agent runtime for controlled operations.
- More mature observability around production SLOs and sustained lag behavior.
- Stronger target-hardware sizing evidence rather than only local benchmark evidence.

### Release engineering gaps

- Packaging is good enough for staged delivery, but still not the final complete installer story.
- Multi-node cluster behavior needs to be validated before claiming enterprise-grade rollout maturity.

## 3. What Is Safe To Release Now

The platform is safe to release now as an open-source, self-hosted, single-node or site-local product for pilot and controlled production use, provided the operator accepts the current constraints.

Safe now:

- single-site pilot installs
- plant-local installs with local ownership of Kafka, historian, and model endpoints
- read-only semantic graph and retrieval context
- backup/restore workflows
- benchmark and soak regression tracking
- local or company-managed model endpoints

Not safe to claim yet:

- fully validated multi-site enterprise rollout at scale
- universal vendor/device compatibility
- target-hardware performance guarantees
- production-grade autonomous action agents

## 4. What Should Wait For Pilot Deployments

- cross-site federation beyond approved summaries and rollups
- production action agents
- enterprise-wide model promotion policy
- strong throughput or latency claims on real plant networks
- final installer/package UX decisions that depend on customer deployment patterns

## 5. Current Verdict

The platform is now past prototype stage and into pilot-ready territory.

It is:

- production-grade in architecture for the semantic plane
- credible for single-site and plant-local self-hosted deployment
- benchmarked against realistic industrial-shaped data

It is still not:

- a fully validated enterprise multi-site industrial platform
- a final release candidate for every vendor and topology

The remaining work is real-world deployment validation, not another large internal refactor.

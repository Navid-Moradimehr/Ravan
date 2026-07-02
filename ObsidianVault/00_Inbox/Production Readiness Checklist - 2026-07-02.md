# Production Readiness Checklist - 2026-07-02

## Purpose

Track what is complete, what is incomplete, and what remains necessary before the platform is treated as production-ready for industrial self-hosting.

Packaging and installer work is intentionally not part of this phase.

## Complete

- multi-protocol ingest, normalization, replay, and historian write paths
- stream separation by site / source / asset identity
- historian read-path guardrails
- Kafka producer reuse and manual consumer commits
- WebSocket live UI updates
- real-time preview and replay tooling
- RBAC, audit logging, authentication, and user-management foundations
- JWT default placeholder is length-safe and auth status reports secret strength
- site-aware project manifest and rollout scaffolding
- project-manifest rollout acceptance command for combined release-gate and benchmark checks
- failure isolation between sites, sources, and correlation groups is enforced by manifest validation
- model gateway abstraction for open-weight and OpenAI-compatible backends
- read-only agent infrastructure
- local and site-oriented benchmark harnesses
- real-world simulator benchmark runner for mock and mixed industrial replay cases
- site-profile benchmark matrix for per-site acceptance runs
- site-profile benchmark calibration reports for per-site sizing recommendations
- CGR gap report command for comparing local measurements against the public CGR streaming claim
- Docker-backed historian write validation for the local replay path
- JSON hot-path simplification for the default serializer path
- dataset conversion workflow for AI4I, C-MAPSS, and generic industrial CSV slices
- synthetic and replay datasets for regression tests
- expanded observability for historian query latency, broker lag, and WebSocket delivery lag
- every manifest source is explicitly attached to a site boundary
- mutating API requests require a bearer token by default and the API emits baseline security headers

## Incomplete

- per-site production benchmarking on target broker and historian topology
- live benchmark calibration on the target industrial network
- model evaluation lifecycle and promotion workflow
- diagnostic-agent runtime
- supervised action-agent runtime
- broader connector and vendor validation against actual devices
- enterprise rollout validation across branches, plants, and subnets
- live industrial-network historian sizing and broker latency validation on customer topology

## Foundation Only

- embeddings and retrieval backend
- prompt and model registries
- read-only agent tooling
- deterministic retrieval/search boundary

## Necessary Changes

1. Complete target-site sizing benchmarks on real broker and historian instances.
2. Validate vendor connectors against real PLC and sensor traffic.
3. Add model evaluation and promotion lifecycle controls.
4. Finish diagnostic-agent and supervised action-agent runtime paths.
5. Keep adding target-site broker/historian p99 probes so the CGR comparison eventually covers real plant latency, not only local replay latency.

## Real-World Simulator Benchmark Plan

- baseline mixed replay pack
- scenario-engine failure cases
- near-real datasets
- local broker/historian validation
- target-site replay and soak tests
- combined release-gate and benchmark acceptance reports
- CGR gap report and gap ratios for local benchmark packs
- replay p99 latency probes for the local benchmark stack

## Links

- [Repo checklist](../../docs/production-readiness-checklist.md)
- [Implementation graph](Implementation Graph - 2026-07-02.md)

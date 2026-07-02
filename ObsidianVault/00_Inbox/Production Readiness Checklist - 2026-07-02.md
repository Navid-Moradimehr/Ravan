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
- model gateway abstraction for open-weight and OpenAI-compatible backends
- read-only agent infrastructure
- local and site-oriented benchmark harnesses
- real-world simulator benchmark runner for mock and mixed industrial replay cases
- site-profile benchmark matrix for per-site acceptance runs
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
5. Tighten failure isolation between sites, sources, and correlation groups.
6. Build an acceptance suite for multi-branch rollout verification.

## Real-World Simulator Benchmark Plan

- baseline mixed replay pack
- scenario-engine failure cases
- near-real datasets
- local broker/historian validation
- target-site replay and soak tests
- threshold-based acceptance reports

## Links

- [Repo checklist](../../docs/production-readiness-checklist.md)
- [Implementation graph](Implementation Graph - 2026-07-02.md)

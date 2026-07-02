# Production Readiness Checklist

**Date**: 2026-07-02

This document tracks what is already complete, what is still incomplete, and what remains necessary before the platform should be treated as an industry-standard industrial rollout package.

Packaging and installer work is intentionally excluded from the current scope.

## Complete

### Runtime and data flow

- Multi-protocol ingest, normalization, replay, and historian write paths exist.
- Stream separation by site / source / asset identity is in place.
- Query guardrails are present for historian read paths.
- Kafka producer reuse and manual consumer offset commit are implemented on the hot paths.
- WebSocket streaming is used for live UI updates.
- Real-time preview and replay tooling exist for local validation.

### Platform foundations

- RBAC, audit logging, authentication, and user-management foundations exist.
- Site-aware project manifest and rollout scaffolding exist.
- Open-weight and OpenAI-compatible model gateway abstraction exists.
- Read-only agent infrastructure exists as a foundation.
- Local and site-oriented benchmark harnesses exist.
- Synthetic and replay datasets are available for regression tests.

### Operational tooling

- Health checks and runtime diagnostics exist.
- Backup and restore tooling exists.
- Metrics and observability paths exist.
- Documentation exists for rollout, benchmark, and testing workflows.

## Incomplete

### Must still be hardened

- Stronger security hardening for shared multi-user deployments.
- Per-site production benchmarking on the actual target broker and historian topology.
- Live benchmark calibration using the target industrial network.
- Model evaluation lifecycle and promotion workflow.
- Diagnostic-agent runtime.
- Supervised action-agent runtime.
- Broader connector/vendor validation against actual devices.
- Enterprise rollout validation across branches, plants, and subnets.

### Foundation-only areas

- Embeddings and retrieval backend are present as a direction, but still need production validation.
- Read-only agent tooling is infrastructure, not a finished agent product.
- Prompt/model registries are infrastructure, not a governance workflow yet.

## Necessary Changes

These are the changes that matter most before calling the platform production-ready for industrial self-hosting.

1. Harden security defaults for multi-user deployments.
2. Complete target-site sizing benchmarks on real broker and historian instances.
3. Validate vendor connectors against real PLC and sensor traffic.
4. Add model evaluation and promotion lifecycle controls.
5. Finish the diagnostic-agent and supervised action-agent runtime paths.
6. Expand observability around broker lag, historian latency, and WebSocket delivery delay.
7. Tighten failure isolation between sites, sources, and correlation groups.
8. Build an acceptance suite for multi-branch rollout verification.

## Real-World Simulator Benchmark Plan

### Goals

- Reproduce plant-like traffic locally.
- Measure throughput, latency, and failure handling under realistic load mixes.
- Compare baseline and hardened runtime behavior.
- Validate that multiple PLCs, sensors, and sites remain logically separated while still supporting correlations.

### Data sources

- `data/benchmarks/industrial_mixed_benchmark.csv`
- built-in mock generator output
- scenario-engine output
- AI4I 2020
- NASA C-MAPSS
- bearing degradation datasets
- SWaT / WADI style telemetry

### Benchmark scenarios

1. Single-site baseline.
2. Multi-PLC single-line traffic.
3. Multi-line plant traffic.
4. Multi-site traffic with shared corporate reporting.
5. Burst load and broker backpressure.
6. Dropout and reconnect scenarios.
7. Degradation and anomaly-heavy scenarios.
8. Historian retention and query pressure.
9. UI fan-out under live stream load.

### Measurements

- end-to-end events per second
- ingest latency p95 / p99
- processor batch commit latency
- historian write latency
- broker lag
- DLQ rate
- WebSocket delivery lag
- CPU and memory consumption
- replay correctness and data separation

### Method

1. Replay the mixed benchmark pack locally as the baseline.
2. Run scenario-based synthetic loads to generate controlled failure cases.
3. Replay near-real datasets to validate distribution and signal shape.
4. Run the same packs against the target broker and historian topology.
5. Compare baseline versus hardened runs.
6. Record acceptance thresholds per site profile.

### Output

- per-scenario benchmark table
- pass/fail against acceptance thresholds
- regression notes
- site-sizing recommendation
- rollout readiness summary


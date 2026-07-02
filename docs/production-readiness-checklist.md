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
- JWT default placeholder is length-safe and auth status reports secret strength.
- Site-aware project manifest and rollout scaffolding exist.
- Project-manifest rollout acceptance command exists for combined release-gate and benchmark checks.
- Open-weight and OpenAI-compatible model gateway abstraction exists.
- Read-only agent infrastructure exists as a foundation.
- Local and site-oriented benchmark harnesses exist.
- Explicit `runtime.mode` contract exists for `python-fallback`, `flink-local`, and `flink-production`.
- `datastreamd` now uses `runtime.mode` to select the default processor set.
- Production-pipeline benchmark command exists so the selected runtime mode can be measured directly.
- Real-world simulator benchmark runner now exists for mock and mixed industrial replay cases.
- Site-profile benchmark matrix exists for per-site acceptance runs.
- Site-profile benchmark calibration reports exist for per-site sizing recommendations.
- CGR gap report command exists for comparing repo measurements against the public CGR streaming claim.
- Dedicated Flink runtime benchmark path exists so the distributed processor contract is measured separately from the Python fallback path.
- Dedicated Flink job image now exists for the compose deployment path.
- Flink keyed-window state now uses the shared rolling-window contract instead of the slower list-and-pop benchmark shape.
- Optional MsgPack wire-format support now exists for the industrial event contract.
- Dataset conversion workflow exists for AI4I, C-MAPSS, and generic industrial CSV slices.
- Failure isolation between sites, sources, and correlation groups is enforced by manifest validation.
- Synthetic and replay datasets are available for regression tests.
- Observability now includes historian query latency, result sizing, broker consumer lag, and WebSocket delivery lag metrics.
- Every manifest source is explicitly attached to a site boundary.
- Mutating API requests now require a bearer token by default, and the API adds baseline security headers.

### Operational tooling

- Health checks and runtime diagnostics exist.
- Backup and restore tooling exists.
- Metrics and observability paths exist.
- Documentation exists for rollout, benchmark, and testing workflows.
- Industrial benchmark comparison report exists for readiness interpretation.

## Incomplete

### Must still be hardened

- Per-site production benchmarking on the actual target broker and historian topology.
- Live benchmark calibration using the target industrial network.
- Production-pipeline validation against the real Flink/Kafka/Timescale deployment topology.
- Repeatability checks over several benchmark sessions to separate regression noise from actual performance loss.
- Model evaluation lifecycle and promotion workflow.
- Diagnostic-agent runtime.
- Supervised action-agent runtime.
- Broader connector/vendor validation against actual devices.
- Enterprise rollout validation across branches, plants, and subnets.

### Foundation-only areas

- Embeddings and retrieval backend are present as a direction, but still need production validation.
- Read-only agent tooling is infrastructure, not a finished agent product.
- Prompt/model registries are infrastructure, not a governance workflow yet.
- Spark support is intentionally optional and should remain a user-managed integration for batch/lakehouse workloads, not a core streaming dependency.

## Necessary Changes

These are the changes that matter most before calling the platform production-ready for industrial self-hosting.

1. Complete target-site sizing benchmarks on real broker and historian instances.
2. Validate vendor connectors against real PLC and sensor traffic.
3. Add model evaluation and promotion lifecycle controls.
4. Finish the diagnostic-agent and supervised action-agent runtime paths.
5. Keep adding target-site broker/historian p99 probes so the CGR comparison eventually covers real plant latency, not only local replay latency.
6. Treat benchmark session deltas as first-class evidence. A single local run can move 1-12 percent on the same machine, so use repeated runs and median/percentile tracking before calling a change a real regression.
7. Keep the streaming hot path on Flink and reserve Spark for optional offline ETL and lakehouse jobs.
8. Treat the wire format as a lever, not a cure-all. If JSON remains faster in Python on the target host, move the hot path into a compiled runtime before forcing binary serialization everywhere.
9. Use the explicit runtime mode contract to keep `python-fallback` for local development and `flink-production` for real rollout targets.
10. Keep the supervisor and deployment templates aligned so runtime mode changes both the active processor and the benchmark baseline.

## Session Delta Guidance

- When a new session is slower by less than about 5 percent, treat it as noise until you repeat the run.
- When the slowdown is in the 5-15 percent range, inspect CPU contention, memory pressure, and benchmark mix changes.
- When a slowdown is above 15 percent, treat it as a likely regression and bisect the last code or environment change.
- When reporting improvements, always include both the absolute numbers and the percentage delta versus the previous recorded session.
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
- project-manifest rollout acceptance command output

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
- combined release-gate and benchmark acceptance report
- [real-world PLC and sensor simulation sources](real-world-plc-sensor-simulation.md)

# Production Readiness Checklist

**Date**: 2026-07-03

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
- API realtime/WebSocket logic has been split out of `services/api_service/main.py`.
- Edge ingest settings, publisher, and protocol connectors are split into focused modules.
- Remaining API router domains are split into focused modules and thin aggregators.

### Platform foundations

- RBAC, audit logging, authentication, and user-management foundations exist.
- JWT default placeholder is length-safe and auth status reports secret strength.
- Site-aware project manifest and rollout scaffolding exist.
- Project-manifest rollout acceptance command exists for combined release-gate and benchmark checks.
- Open-weight and OpenAI-compatible model gateway abstraction exists.
- Read-only agent infrastructure exists as a foundation.
- Logical metadata plane snapshot exists and unifies schema, model, prompt, dataset, retrieval, semantic, and lineage metadata without adding a new runtime service.
- Asset registry snapshot and canonical event catalog snapshots exist for rollout validation without adding another service boundary.
- Governance snapshot exists for schema/model/prompt lifecycle without introducing a workflow engine.
- Metadata artifacts now persist to JSON bundles for release-gate and rollout-acceptance archives.
- Metadata-plane snapshot benchmarking exists so snapshot overhead can be tracked alongside runtime and pipeline benchmarks.
- Logical operational-memory snapshot exists and aggregates alerts, annotations, shifts, reports, and backup readiness without adding a MES-like workflow engine.
- Logical site-observability snapshot exists and reports broker, historian, AI, backup, and API health with SLO targets for each deployment mode.
- Dedicated lineage snapshot route exists and emits an OpenLineage-style read-only view over semantic lineage.
- Local Kubernetes rehearsal exists for generated site bundles.
- The diagnostic/runtime scaffold can be inspected locally through the CLI.
- Local and site-oriented benchmark harnesses exist.
- Production-pipeline repeatability and session-delta reporting exist.
- Explicit `runtime.mode` contract exists for `python-fallback`, `flink-local`, and `flink-production`.
- `datastreamd` now uses `runtime.mode` to select the default processor set.
- Production-pipeline benchmark command exists so the selected runtime mode can be measured directly.
- Helm chart and generated site bundles now select the processor path or the Flink job from the same runtime-mode contract.
- Real-world simulator benchmark runner now exists for mock and mixed industrial replay cases.
- Site-profile benchmark matrix exists for per-site acceptance runs.
- Site-profile benchmark calibration reports exist for per-site sizing recommendations.
- CGR gap report command exists for comparing repo measurements against the public CGR streaming claim.
- Dedicated Flink runtime benchmark path exists so the distributed processor contract is measured separately from the Python fallback path.
- Dedicated Flink job image now exists for the compose deployment path.
- Flink keyed-window state now uses the shared rolling-window contract instead of the slower list-and-pop benchmark shape.
- Optional MsgPack wire-format support now exists for the industrial event contract.
- Optional Rust fastpath module now exists for JSON bytes and partition-key handling, but it is opt-in and not the default runtime path.
- Dataset conversion workflow exists for AI4I, C-MAPSS, and generic industrial CSV slices.
- Historian batch/query plumbing is now consolidated behind shared helpers.
- API and AI gateway health surfaces report degraded mode instead of swallowing repeated runtime failures.
- The Flink job now tolerates malformed records and supports configurable starting offsets.
- Failure isolation between sites, sources, and correlation groups is enforced by manifest validation.
- Synthetic and replay datasets are available for regression tests.
- Observability now includes historian query latency, result sizing, broker consumer lag, and WebSocket delivery lag metrics.
- Every manifest source is explicitly attached to a site boundary.
- Mutating API requests now require a bearer token by default, and the API adds baseline security headers.

### Operational tooling

- Health checks and runtime diagnostics exist.
- Backup and restore tooling exists.
- Backup-drill matrix tooling exists so restore/rollback drills can be measured per site profile.
- Site profile backups now carry explicit backup-owner and restore-drill-owner fields.
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
- Diagnostic-agent productization beyond the scaffold.
- Supervised action-agent productization beyond the scaffold.
- Broader connector/vendor validation against actual devices.
- Enterprise rollout validation across branches, plants, and subnets.
- Further package cleanup is still possible, but the major runtime splits are in place.
- The current host still shows benchmark variance large enough that small code changes should be treated as neutral until repeated.
- The compiled boundary experiment should stay opt-in unless it is revalidated on target hardware.

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
4. Finish the diagnostic-agent and supervised action-agent productization paths.
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


## Production-Hardening Refactor (2026-07-06)

Completed a six-phase architecture refactor for open-source production readiness:

- [x] **Phase 1** — Edge ingest backpressure and overload handling (bounded MQTT queue, oversize/DLQ routing).
- [x] **Phase 2** — Sink abstractions (`Sink` protocol, `CompositeSink`, `SinkRegistry`, historian + Kafka sinks).
- [x] **Phase 3** — Normalized fan-out consumer decouples the edge publisher from the historian; event-id dedup; composite keying.
- [x] **Phase 4** — Flink/Python runtime parity (ProcessedEventsSink, state-eviction fix, batched producer drain, composite key).
- [x] **Phase 5** — Iceberg lakehouse sink on MinIO (ADR 0003).
- [x] **Phase 6** — AI-enriched fan-out persistence, push-driven dashboard bus, schema governance.

Each phase shipped as one conventional commit with code, tests, implementation-log entry, and Obsidian vault updates so the repo is green at every step.

## Competitive-Inspiration Hardening (2026-07-06)

After comparing the platform against a similar managed streaming product (`comparission.md`), three app-layer inspirations were implemented (Redpanda intentionally excluded; we use Kafka in KRaft mode). Full evaluation in `ObsidianVault/10_PRD/Competitive Comparison Evaluation.md`:

- [x] **Inspiration 1** — Schema registry compatibility enforcement: `BACKWARD`/`FORWARD`/`FULL`/`NONE` modes on the registry so breaking schema evolution is rejected at registration time (default `BACKWARD`). Optional file-backed state via `SCHEMA_REGISTRY_PATH` keeps compatibility history across restarts. 14 tests in `tests/test_schema_registry_compat.py`.
- [x] **Inspiration 1b** — Model registry and prompt registry durability: optional file-backed state via `MODEL_REGISTRY_PATH` and `PROMPT_REGISTRY_PATH` keeps AI bindings and prompt templates across restarts without adding a new metadata service. New tests in `tests/test_modeling_contracts.py`.
- [x] **Inspiration 1c** — Dataset catalog durability: optional file-backed state via `DATASET_CATALOG_PATH` keeps benchmark and release-candidate dataset catalogs stable across restarts without adding a new service boundary. New tests in `tests/test_datastreamctl.py`.
- [x] **Inspiration 1d** — Asset CRUD durability: optional file-backed state via `ASSET_STORE_PATH` or `ASSET_REGISTRY_PATH` keeps asset edits and tags across restarts for single-node installs. New tests in `tests/test_asset_store.py`.
- [x] **Inspiration 1e** — Operational-memory durability: optional file-backed state via `COLLABORATION_STORE_PATH`, `ALERT_MANAGER_PATH`, and `REPORT_TEMPLATE_STORE_PATH` keeps annotations, alert lifecycle state, and report templates across restarts. New tests in `tests/test_operational_memory_persistence.py`.
- [x] **Inspiration 1f** — Report schedule rehydration: persisted report templates now store recurring schedules and restore them when the schedule library is available, so recurring exports survive restarts without adding a workflow engine.
- [x] **Report** — The postponed-features matrix is documented in `docs/postponed-features.md` and mirrored in Obsidian vault at `ObsidianVault/20_Architecture/Postponed Features Matrix.md`.
- [x] **Report** — Agent integration guidance is documented in `docs/agent-integration-guidance.md` and mirrored in Obsidian vault at `ObsidianVault/20_Architecture/Agent Integration Guidance.md`.
- [x] **Inspiration 2** — MQTT QoS, retained availability, and Last-Will support in the edge-ingest connector. Configurable via `MQTT_QOS`, `MQTT_RETAINED`, and `MQTT_WILL_*` env vars. 5 tests in `tests/test_mqtt_qos_will.py`.
- [x] **Inspiration 3** — Delivery chaos / replay dedup coverage: tests that simulate a mid-batch consumer crash + Kafka redelivery and assert the at-least-once fan-out plus `ON CONFLICT (event_id) DO NOTHING` dedup produces no duplicate historian rows. 3 tests in `tests/test_delivery_chaos.py`.

Each inspiration shipped as one conventional commit with code, tests, implementation-log entry, and vault updates.

### Medium-effort inspirations (also implemented)

The competitive evaluation originally flagged three medium-effort inspirations as config/docs-only future work. All three had positive production impact and are now implemented:

- [x] **Inspiration 4** — Flink checkpoint + state-backend config: exactly-once checkpoints, RocksDB state backend with incremental checkpoints, externalized retained cleanup. A job restart now resumes from the last checkpoint instead of losing keyed window state. Env-configurable; 10 tests in `tests/test_flink_checkpoint_config.py`.
- [x] **Inspiration 5** — Prometheus alert rules: 9 alerts in 4 groups (consumer lag, DLQ/overflow/delivery/reconnect, historian write failures + slow queries, WebSocket delivery lag), all referencing metrics the services emit. Wired into `prometheus.yml` and mounted in compose. 7 tests in `tests/test_prometheus_alert_rules.py`.
- [x] **Inspiration 6** — Debezium PostgreSQL CDC recipe: ready-to-register connector config, idempotent registration script, logical publication. Optional alternative ingest path for relational sources. Runbook in the vault. 7 tests in `tests/test_debezium_cdc_recipe.py`.

### Test-drift reconciliation (2026-07-06)

A full-suite run surfaced nine tests that drifted from earlier refactors (no functionality changed). All reconciled; full suite now 419 passed.

- [x] **TLS tests** repointed at the refactored `connectors/{mqtt,opcua,modbus}.py` modules (3 tests).
- [x] **Historian execute_values mocks** updated to accept the `page_size` kwarg (2 tests).
- [x] **AI gateway service_state** switched from dict syntax to the `ServiceHealthState` object API; also fixed a silent degraded-state reset in `enrich_batch` where `mark_ok()` was called unconditionally after a fallback (1 test + 1 real bug).
- [x] **UI mobile tests** aligned with the Next.js 14 `viewport` export and `sm:`/`md:`/`xl:` breakpoints (2 tests).
- [x] **DLQ ingest test isolation**: `test_historian` env leak fixed via `monkeypatch.setenv`; `_get_producer` lru_cache cleared in the DLQ test (1 test).

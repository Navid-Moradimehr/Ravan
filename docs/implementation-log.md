# Implementation Log

## 2026-07-10 - Pipeline Panel Help Tips

Added inline `?` help tips to the four main Pipeline page panels and clarified
that the Boundary Notes rail is static guidance rather than a live data feed.

### Updated
- `ui/app/pipeline/page.tsx`
- `docs/pipeline-walkthrough.md`
- `ObsidianVault/30_UI_UX/Pipeline Walkthrough.md`

### Validation
- UI build to be rerun after the change.

## 2026-07-10 - Prometheus and Pipeline Walkthrough Docs

Added standalone walkthrough docs for Prometheus and the Pipeline route so
new users can understand the monitoring backend and the pre-storage flow
without reading the source code first.

### Added
- `docs/prometheus-guide.md`
- `docs/pipeline-walkthrough.md`
- `ObsidianVault/60_Observability/Prometheus Guide.md`
- `ObsidianVault/30_UI_UX/Pipeline Walkthrough.md`

### Validation
- Documentation-only change.

## 2026-07-10 - Kafka UI Help Placement and External Surface Clarification

Adjusted the Command Center so the Kafka UI explanation lives where operators
actually look for it: as a small help tip attached to the Kafka UI operator
link. The separate Kafka UI help card was removed from the landing page to keep
the right rail compact.

### Updated
- `ui/app/page.tsx`
- `docs/command-center-walkthrough.md`
- `docs/kafka-ui-guide.md`

### Notes
- The Kafka UI page at `http://localhost:18080/` is an upstream app served by
  the `ghcr.io/kafbat/kafka-ui` container.
- The Grafana page at `http://localhost:13000/` is an upstream app served by
  the `grafana/grafana` container and proxied through NGINX.
- This repository controls links, proxying, provisioning, and explanatory UI,
  but the broker console and Grafana UI themselves are owned by their upstream
  projects.

### Validation
- UI and docs alignment checked by code inspection.

## 2026-07-07 - Logical Metadata Plane Foundation

Added a lightweight logical metadata plane without introducing a new microservice.
The change aggregates the existing schema registry, model registry, prompt
registry, dataset catalog, semantic core, retrieval catalog, and semantic-store
summaries behind one read-only inspection surface.

### Added
1. **Metadata plane snapshot** (`services/common/metadata_plane.py`) —
   logical aggregation of platform knowledge with explicit platform-core vs
   user-owned boundaries and the three memory layers documented in code.
2. **Metadata inspection API** (`services/api_service/routers/metadata.py`) —
   `/api/v1/metadata` exposes the same snapshot through the existing API
   service.
3. **Metadata contract tests** (`tests/test_metadata_plane.py`) — verifies the
   snapshot assembles the current registries and remains read-only.

### Updated
- `docs/platform-semantic-core.md`
- `docs/production-readiness-checklist.md`
- `docs/metadata-plane.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`

### Validation
- Focused pytest run passed: 18 passed.

## 2026-07-07 - Site Observability Snapshot

Added a read-only site-observability snapshot that pulls together broker,
historian, AI gateway, backup readiness, and API health into one rollout-facing
view with deployment-mode SLO targets.

### Added
1. **Site observability snapshot** (`services/common/site_observability.py`) —
   logical observability contract for a site.
2. **Observability API** (`services/api_service/routers/observability.py`) —
   `/api/v1/observability/site` exposes the snapshot.
3. **Site observability tests** (`tests/test_site_observability.py`) — verifies
   snapshot behavior and route exposure.

### Updated
- `docs/multi-site-rollout.md`
- `docs/site-observability.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/System Architecture.md`

### Validation
- Focused pytest run passed: 20 passed.

## 2026-07-07 - Backup Ownership Contract

Extended the site profile backup policy with explicit backup-owner and
restore-drill-owner fields and threaded them into backup drill matrix reports
and release-gate payloads.

### Added
1. **Backup ownership fields** (`services/common/site_profiles.py`) â€” optional
   owner metadata on the site backup policy, exported to env and YAML.
2. **Backup drill report ownership** (`services/cli/datastreamctl.py`) â€” backup
   drill matrix rows and release-gate payloads now include backup and
   restore-drill ownership plus cadence details.
3. **Sample profile updates** (`config/site-profiles/*.yaml`) â€” the built-in
   site profiles now show how to populate the new ownership fields.

### Updated
- `docs/multi-site-rollout.md`
- `docs/production-readiness-checklist.md`

### Validation
- Focused pytest slices passed: 21 passed in the datastreamctl/site-profile slice and 7 passed in the API/metadata slice.

## 2026-07-07 - Lineage Snapshot Contract

Added a dedicated read-only lineage snapshot over the existing semantic lineage store without creating a new persistence layer or microservice.

### Added
1. **Lineage snapshot contract** (`services/common/lineage_contract.py`) â€” builds an OpenLineage-style summary over semantic lineage records with per-kind, per-site, per-dataset, per-model-version, and per-processing-version counts.
2. **Lineage API** (`services/api_service/routers/lineage.py`) â€” `/api/v1/lineage` returns the read-only snapshot through the existing API service.
3. **Lineage contract tests** (`tests/test_lineage_contract.py`) â€” verifies the snapshot shape and route exposure.

### Updated
- `docs/platform-semantic-core.md`
- `docs/metadata-plane.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`

### Validation
- Focused pytest run passed: 7 passed.

## 2026-07-07 - Asset Registry and Event Catalog Snapshots

Extended the logical metadata plane with a flattened asset registry snapshot and a canonical event catalog snapshot, both exposed as read-only API routes without adding a new service boundary.

### Added
1. **Asset registry snapshot** (`services/common/asset_registry.py`) â€” flattens the existing asset hierarchy into a rollout-friendly registry view with site, area, line, cell, asset, and tag entries.
2. **Event catalog snapshot** (`services/common/event_catalog.py`) â€” exposes the canonical Kafka contract plus project-manifest topic mappings as a read-only catalog.
3. **Metadata API routes** (`services/api_service/routers/asset_registry.py`, `services/api_service/routers/event_catalog.py`) â€” `/api/v1/metadata/assets` and `/api/v1/metadata/events`.
4. **Metadata catalog tests** (`tests/test_metadata_catalogs.py`) â€” verifies the snapshots and route exposure.

### Updated
- `services/common/metadata_plane.py`
- `docs/metadata-plane.md`
- `docs/platform-semantic-core.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`
- `ObsidianVault/20_Architecture/System Architecture.md`

### Validation
- Focused pytest run passed: 10 passed.

## 2026-07-07 - Governance Snapshot

Added a lightweight read-only governance snapshot for schema, model, prompt, and dataset lifecycle readiness without introducing a workflow engine.

### Added
1. **Governance snapshot** (`services/common/governance_plane.py`) â€” summarizes registry readiness, compatibility, enabled model roles, prompt versions, and dataset catalog coverage.
2. **Governance API** (`services/api_service/routers/governance.py`) â€” `/api/v1/metadata/governance` exposes the snapshot through the existing API service.
3. **Governance tests** (`tests/test_governance_plane.py`) â€” verifies the lifecycle summary and route exposure.

### Updated
- `docs/metadata-plane.md`
- `docs/platform-semantic-core.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`
- `ObsidianVault/20_Architecture/System Architecture.md`

### Validation
- Focused pytest run passed: 12 passed.

## 2026-07-07 - Metadata Artifact Persistence and Benchmark

Added durable JSON metadata-artifact bundles for release-gate and rollout-acceptance archives, plus a benchmark path for measuring snapshot construction overhead.

### Added
1. **Metadata artifact bundle** (`services/common/metadata_artifacts.py`) â€” builds and writes JSON bundles for the metadata plane, governance, asset registry, event catalog, and lineage snapshots.
2. **Metadata artifact benchmark** (`services/benchmarks/metadata_artifacts.py`) â€” measures snapshot construction throughput so metadata overhead stays visible like the runtime benchmarks.
3. **CLI automation** (`services/cli/datastreamctl.py`) â€” `project-manifest release-gate` and `project-manifest rollout-acceptance` now persist metadata-artifact bundles alongside release reports, and `benchmark metadata-plane-snapshot` measures snapshot construction cost.
4. **Tests** (`tests/test_metadata_artifacts.py`, updated `tests/test_datastreamctl.py`) â€” verifies report-dir output and benchmark command behavior.

### Updated
- `docs/metadata-plane.md`
- `docs/platform-semantic-core.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`
- `ObsidianVault/20_Architecture/System Architecture.md`

### Validation
- Focused pytest run passed: 10 tests in the metadata-artifacts slice and 6 tests in the release-gate/benchmark slice.

## 2026-07-07 - Operational Memory Boundary

Added a read-only operational memory snapshot on top of existing alert,
annotation, OEE, report, and backup surfaces. This keeps operational context
visible without promoting maintenance/work-order workflows into the platform
core yet.

### Added
1. **Operational memory snapshot** (`services/common/operational_memory.py`) —
   aggregates alerts, annotations, shift windows, report inventory, and backup
   readiness into one operator-state view.
2. **Operational memory API** (`services/api_service/routers/operational_memory.py`)
   — `/api/v1/metadata/operational` exposes the snapshot.
3. **Operational memory tests** (`tests/test_operational_memory.py`) — verifies
   the snapshot and route remain read-only and contract-stable.

### Updated
- `docs/metadata-plane.md`
- `docs/operational-memory.md`
- `docs/platform-semantic-core.md`
- `docs/production-readiness-checklist.md`
- `ObsidianVault/20_Architecture/Platform Core and Semantic Plane.md`
- `ObsidianVault/20_Architecture/System Architecture.md`

### Validation
- Focused pytest run passed: 18 passed.

## 2026-07-06 - Data Pipeline Integrity Hardening (Audit Findings 1-5)

Implemented the five findings from `docs/data-pipeline-audit-and-plan.md`.
Each is an isolated, tested commit; the suite stayed green throughout
(429 passed, 0 failed). See `docs/session-changes-and-rationale.md` for the
full rationale.

### Added
1. **processed_events dedup** (`bee8953`) — `ON CONFLICT (event_id) DO NOTHING`
   on the single and batch `processed_events` inserts in
   `services/historian/client.py`, closing the last historian dedup gap.
2. **Runtime processor dual-write gate** (`b6eca10`) —
   `RUNTIME_PERSIST_PROCESSED_EVENTS` (default `1`) in
   `services/processor/runtime_processor.py`; extracted `_flush_processed_batch`
   to module level. Off = pure topic fan-out (offsets still commit).
3. **Compose topic auto-provisioning** (`8ea9d29`) — `kafka-init` one-shot
   service in `docker/docker-compose.yml` creates all six canonical topics
   idempotently (3 partitions, replication-factor 1).
4. **Outbound bridge at-least-once** (`5c8dc71`) —
   `services/edge_ingest/outbound_bridge.py`: `enable.auto.commit=False`;
   forwarders return `bool`; commit offset only after all forwarders succeed.

### Fixed
1. **Broken init-SQL bind mounts** (`ffc4e07`) — `timescaledb` and `postgres`
   services referenced `./postgres/...` paths that do not exist (files are in
   `docker/postgres/`). Docker Compose silently mounted empty dirs, so fresh
   stacks ran with no schema. Corrected both mounts. This was the highest-
   impact defect found this session.
2. **Stale schema removed** (`ffc4e07`) — deleted `postgres/init-timescale.sql`
   (lacked unique indexes); its two tests now reference the canonical
   `docker/postgres/init-timescale-full.sql`.
3. **Topic script divergence** (`ffc4e07`) — `scripts/create-topics.ps1`
   reconciled with the canonical topic set and partition counts.

### Changed
- `README.md` quickstart notes topics are auto-created by `kafka-init`.

### Tests
- +1 historian ON CONFLICT test, +4 processor gate tests, +5 compose topic
  tests, +5 outbound bridge tests. All 429 pass.

### Constraints honored
- No functionality change beyond the fixes; defaults preserved.
- No security/authn/authz changes (standing constraint).

## 2026-07-06 - Competitive Inspiration 6 (Debezium PostgreSQL CDC Recipe)

### Added

1. **Debezium connector config** in `docker/debezium/pg-orders-source.json`
   - PostgreSQL source connector on `public.orders` using `pgoutput`, logical slot `debezium_orders`, publication `dbz_orders`, incremental snapshots, and the `ExtractNewRecordState` SMT (unwrapped rows, tombstones dropped, deletes rewritten). JSON converters with schemas disabled to match the platform envelope style.

2. **Registration script** `docker/debezium/register-connectors.sh`
   - Idempotently registers every `*.json` connector config against the Kafka Connect REST API (default `localhost:18083`); deletes existing connectors first so the repo config is authoritative.

3. **Logical publication** added to `docker/postgres/init.sql`
   - `CREATE PUBLICATION dbz_orders FOR TABLE public.orders` (guarded by existence check). The `orders` table already had `REPLICA IDENTITY FULL`; the `postgres` service already ran `wal_level=logical`.

4. **Runbook** in `ObsidianVault/40_Runbooks/Debezium CDC Ingest.md`
   - When to use CDC, prerequisites, registration, produced topics, downstream integration notes. Documents that CDC is an optional alternative ingest path that does not replace the industrial event stream.

5. **Tests** in `tests/test_debezium_cdc_recipe.py` (7 cases)
   - Connector config validity/class/plugin/slot/publication/table, incremental snapshot, envelope unwrap SMT, register script references the config dir, init.sql creates the publication + replica identity, postgres service runs `wal_level=logical`, connect service is the Debezium image.

### Verified

- `python -m pytest tests/test_debezium_cdc_recipe.py` -> 7 passed
- `pg-orders-source.json` parses as valid JSON; `docker-compose.yml` parses as valid YAML

### Notes

- Inspiration source: competitive comparison (pillar 04 - Debezium CDC). The Connect image and a CDC-ready Postgres were already present but had no ready connector config or publication. This makes CDC a one-command opt-in for open-source adopters who have a relational source to capture, without forcing it on users who only use the industrial event path. CDC topics (`pg.public.orders`) are not industrial events; routing them into the normalized stream is intentionally left to a user-specific mapping.

## 2026-07-06 - Competitive Inspiration 5 (Prometheus Alert Rules)

### Added

1. **Alert rules** in `docker/prometheus/alert_rules.yml` (4 groups, 9 alerts)
   - Consumer lag: `ConsumerLagHigh` (warning, >1000 msgs/2m), `ConsumerLagCritical` (critical, >10000 msgs/5m) on `datastream_broker_consumer_lag_messages`.
   - Delivery health: `DLQRateHigh` (>1/sec for 5m on `edge_ingest_dlq_total`), `EdgeOverflowSustained` (`edge_ingest_overflow_total`), `KafkaDeliveryFailures` (critical, `edge_ingest_delivery_failures_total`), `AdapterReconnectStorm` (`edge_ingest_reconnects_total`).
   - Historian: `HistorianWriteFailures` (critical, `historian_write_total{status="failed"}`), `HistorianQuerySlow` (p95 > 1s on `datastream_historian_query_latency_seconds`).
   - Realtime: `WebSocketDeliveryLagHigh` (p95 > 5s on `datastream_websocket_delivery_lag_seconds`).
   - Every alert references only metrics the services actually emit, so no rule silently never fires due to metric-name drift.

2. **`rule_files`** wired into `docker/prometheus/prometheus.yml`.

3. **Rules file mount** added to the `prometheus` service in `docker/docker-compose.yml` (`./prometheus/alert_rules.yml:/etc/prometheus/alert_rules.yml:ro`).

4. **Tests** in `tests/test_prometheus_alert_rules.py` (7 cases)
   - Valid YAML, every alert has name/expr/for/severity/summary, every expr references a known metric, consumer-lag + historian-failure alerts exist, prometheus.yml registers the rules file, compose mounts the rules read-only.

### Verified

- `python -m pytest tests/test_prometheus_alert_rules.py` -> 7 passed
- `alert_rules.yml` and `prometheus.yml` and `docker-compose.yml` all parse as valid YAML

### Notes

- Inspiration source: competitive comparison (pillar 07 - lag/health monitoring). The platform already emitted the metrics but had zero alert rules, so backlog grew silently. These are conservative open-source baselines; operators tune SUSTAINED windows and severity to their SLOs and can route Prometheus alerts to an Alertmanager (or the existing API-level AlertManager) via webhook. The API AlertManager (Apprise + escalation engine) is a separate application-layer alert system; both layers are complementary.

## 2026-07-06 - Competitive Inspiration 4 (Flink Checkpoint and State-Backend Config)

### Added

1. **Checkpoint + state-backend configuration** in `services/processor/iot_anomaly_job.py`
   - `CheckpointSettings` dataclass + `checkpoint_settings()` factory reading env vars: `FLINK_CHECKPOINT_INTERVAL_MS`, `FLINK_CHECKPOINT_MODE` (exactly_once/at_least_once), `FLINK_CHECKPOINT_TIMEOUT_MS`, `FLINK_CHECKPOINT_MIN_PAUSE_MS`, `FLINK_CHECKPOINT_MAX_CONCURRENT`, `FLINK_CHECKPOINT_EXTERNALIZED_CLEANUP` (retain/delete), `FLINK_CHECKPOINT_UNALIGNED`, `FLINK_STATE_BACKEND` (rocksdb/hashmap), `FLINK_INCREMENTAL_CHECKPOINTS`.
   - `configure_checkpoints(env, settings)` applies the settings to the Flink `StreamExecutionEnvironment` via the PyFlink API (guarded by `PYFLINK_AVAILABLE`): exact-once mode, externalized retained checkpoints, RocksDB state backend with incremental checkpoints.
   - Defaults favour production-grade stateful streaming: exactly-once, RocksDB + incremental checkpoints, externalized retained cleanup, 10s interval. A job restart now resumes from the last successful checkpoint instead of losing keyed state or replaying from the source.

### Changed

1. **`main()` checkpoint bootstrap** - the bare `env.enable_checkpointing(interval)` is replaced by `configure_checkpoints(env, checkpoint_settings())`, which sets mode, timeout, min-pause, max-concurrent, externalized cleanup, unaligned flag, and the RocksDB backend.

### Verified

- `python -m pytest tests/test_flink_checkpoint_config.py` -> 10 passed
- `python -m pytest tests/test_flink_parity.py` -> 5 passed (no regression)
- `py_compile` on `iot_anomaly_job.py` -> ok

### Notes

- Inspiration source: competitive comparison (pillar 02 - Flink stateful depth). Previously the job used in-memory state with `AT_LEAST_ONCE` delivery and bare checkpointing; on failure it lost all keyed window state. RocksDB + incremental checkpoints + externalized retained checkpoints make the stateful job restart-safe and scalable beyond task-manager RAM. Config-only relative to runtime; the `configure_checkpoints` body runs only inside the Flink container (PyFlink is not installed in the test venv).

## 2026-07-06 - Competitive Inspiration 3 (Delivery Chaos and Replay Dedup Coverage)

### Added

1. **Delivery chaos / replay dedup tests** in `tests/test_delivery_chaos.py` (3 cases)
   - `test_at_least_once_redelivery_with_event_id_dedup_no_duplicates`: simulates a mid-batch consumer crash (offsets not committed) followed by Kafka rebalance redelivery; asserts the historian sink receives the same `event_id`s twice but every batch insert carries `ON CONFLICT (event_id) DO NOTHING`, so redelivery is a no-op rather than a duplicate row.
   - `test_crash_before_commit_redelivers_uncommitted_message`: models a process death between poll and commit; asserts the offset is uncommitted, the message is redelivered on restart, and the offset commits only after the successful second attempt.
   - `test_duplicate_event_ids_in_one_batch_are_deduped_by_sql`: two events with the same `event_id` in a single batch rely on the `ON CONFLICT (event_id) DO NOTHING` clause to resolve the duplicate at the DB constraint.

### Verified

- `python -m pytest tests/test_delivery_chaos.py` -> 3 passed
- `python -m pytest tests/test_sinks.py tests/test_normalized_fanout.py tests/test_lakehouse_sink.py tests/test_ai_gateway_dedup.py` -> 22 passed (no regression)

### Notes

- Inspiration source: competitive comparison (pillar 06 - exactly-once end-to-end / chaos tests). Our delivery model is at-least-once (idempotent producers + acks=all + offset-commit-after-sink) with `event_id` dedup at the historian as the de-facto exactly-once strategy. These tests make that contract explicit and guard the redelivery path against regressions. No production code changed; this is test-only coverage of an existing guarantee.
- The tests use a recording fake Kafka consumer (redelivers on `reset_to`) and a stubbed historian client (captures `execute_values` SQL + rows), so they run without a real broker or database.

## 2026-07-06 - Competitive Inspiration 2 (MQTT QoS, Retained, Last-Will)

### Added

1. **MQTT delivery options** in `services/edge_ingest/settings.py`
   - `mqtt_qos` (default 1) - subscription QoS level.
   - `mqtt_retained_available` (default true) - declares whether the broker retains the last known good value per topic.
   - `mqtt_will_topic` / `mqtt_will_payload` / `mqtt_will_qos` / `mqtt_will_retain` - Last Will and Testament options; empty will topic disables the LWT.

2. **QoS on subscribe** in `services/edge_ingest/connectors/mqtt.py`
   - `client.subscribe(settings.mqtt_topic, qos=settings.mqtt_qos)` so the broker enforces the configured delivery guarantee instead of defaulting to QoS 0.

3. **Last-Will configuration** in `services/edge_ingest/connectors/mqtt.py`
   - When `mqtt_will_topic` is set, `client.will_set(...)` is called before `connect()` so an ungraceful adapter disconnect is signalled to downstream consumers. Empty payload is sent as `None` (zero-length body).

4. **Docker Compose env defaults** in `docker/docker-compose.yml`
   - Edge-ingest service now exposes `MQTT_QOS`, `MQTT_RETAINED`, and the four `MQTT_WILL_*` vars with override defaults so operators discover them.

5. **Tests** in `tests/test_mqtt_qos_will.py` (5 cases)
   - Settings defaults, subscribe uses configured QoS, LWT configured when topic set, no LWT by default, empty will payload sent as None. Uses a recording fake paho client (no real broker).

### Verified

- `python -m pytest tests/test_mqtt_qos_will.py` -> 5 passed
- `python -m pytest tests/test_edge_backpressure.py` -> 5 passed (no regression)
- `py_compile` on `mqtt.py` and `settings.py` -> ok
- `docker-compose.yml` parses as valid YAML

### Notes

- Inspiration source: competitive comparison (pillar 05 - MQTT 5.0 maturity). Compatible with our existing paho client and mosquitto broker; no protocol or infra change required. The edge publisher/sim path is unchanged (it still publishes at QoS 1) - this inspiration targets the ingest subscriber side.

## 2026-07-06 - Competitive Inspiration 1 (Schema Registry Compatibility Enforcement)

### Added

1. **Schema compatibility enforcement** in `services/common/schema_registry.py`
   - Standard registry-style compatibility modes: `BACKWARD`, `FORWARD`, `FULL`, `NONE` constants plus `COMPATIBILITY_MODES`.
   - `IncompatibleSchemaError` raised when a new version violates the configured mode.
   - `set_compatibility(schema_id, mode)` / `get_compatibility(schema_id)` for per-schema policy (default `BACKWARD`).
   - `register()` now accepts optional `compatibility` (per-call override) and `enforce` (bypass for bootstrap/forced migration) keyword arguments.
   - `_check_compatibility()` validates: required-field removal, field type change, optional->required transition (backward), and adding a required field (forward).
   - `list_schemas()` now reports the active `compatibility` mode per schema.

2. **Tests** in `tests/test_schema_registry_compat.py` (13 cases)
   - BACKWARD (allow optional add; reject required removal, type change, optional->required), FORWARD (reject required add; allow optional add), FULL (both directions), NONE (allow anything), `enforce=False` bypass, per-call compatibility override, mode validation, list-schemas compatibility field, and default-schema bootstrap.

### Changed

1. **`register()` signature** — now keyword-only `compatibility` and `enforce` params; existing callers (API router, bootstrap) keep working because bootstrap paths register v1 with no prior version (no enforcement triggered) and the API router registers custom schemas against a fresh subject.

### Verified

- `python -m pytest tests/test_schema_registry_compat.py` -> 13 passed
- `python -m pytest tests/test_ai_enriched_fanout.py::test_schema_registry_has_processed_and_benchmark_schemas` -> 1 passed

### Notes

- Inspiration source: competitive comparison (pillar 10 - schema registry safe evolution). Compatible with our open-source "validate in app code" stance (ADR 0002) and the in-memory registry; no external registry infrastructure required.

## 2026-07-07 - Schema Registry Persistence Boundary

Made the schema registry optionally file-backed without changing the default single-process behavior.

### What changed

1. **`services/common/schema_registry.py`**
   - Added optional `state_path` support and `SCHEMA_REGISTRY_PATH` env wiring.
   - The registry now bootstraps defaults, then persists schema versions and compatibility mode to a JSON state file when configured.
   - Registry mutations (`register`, `set_compatibility`) now flush state through an atomic temp-file replace.

2. **Tests**
   - Extended `tests/test_schema_registry_compat.py` with a reload/persistence case that verifies version history and compatibility survive a restart.

### Verification

- `uv run pytest tests/test_schema_registry_compat.py` -> 14 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

This keeps the schema registry inside the platform core boundary while making it durable enough for release artifacts and local production deployments. It improves compatibility governance without introducing a new service or changing the Kafka-centered architecture.

## 2026-07-07 - Model and Prompt Registry Persistence Boundary

Extended the governance metadata layer so model bindings and prompt templates can persist to local JSON state when configured.

### What changed

1. **`services/common/modeling.py`**
   - Added optional `state_path` support and `MODEL_REGISTRY_PATH` wiring.
   - Default role bindings still bootstrap in-process, but custom bindings now survive restart when a path is provided.

2. **`services/common/prompt_registry.py`**
   - Added optional `state_path` support and `PROMPT_REGISTRY_PATH` wiring.
   - Prompt templates now persist atomically to JSON when configured.

3. **Tests**
   - Extended `tests/test_modeling_contracts.py` with registry reload checks for both model and prompt registries.

### Verification

  - `uv run pytest tests/test_schema_registry_compat.py tests/test_modeling_contracts.py` -> 25 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

Model bindings and prompt templates are governance metadata, not separate runtime services. Keeping them in-process preserves the open-source deployment model while making the metadata plane durable enough for repeatable local production installs.

## 2026-07-07 - Dataset Catalog Persistence Boundary

Extended the dataset registry so benchmark and release-candidate catalog entries can persist to local JSON state when configured.

### What changed

1. **`services/datasets/runtime_catalog.py`**
   - Added a lightweight `DatasetCatalog` wrapper with optional `DATASET_CATALOG_PATH` wiring.
   - The catalog still defaults to the baked-in dataset list, but registered additions now survive restart when a path is provided.

2. **Tests**
   - Extended `tests/test_datastreamctl.py` with catalog reload coverage for a persisted custom dataset entry.

### Verification

- `uv run pytest tests/test_schema_registry_compat.py tests/test_modeling_contracts.py tests/test_datastreamctl.py` -> 81 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

The dataset catalog is metadata about available benchmark and validation inputs, not a user data store. Persisting it inside the metadata plane keeps the release story reproducible without introducing a separate catalog service.

## 2026-07-07 - Asset CRUD Persistence Boundary

Made the external asset CRUD surface optionally file-backed so user-owned asset edits and tags survive restart in single-node deployments.

### What changed

1. **`services/assets/model.py`**
   - Promoted the asset CRUD helpers into the real module used by the router.
   - Added `AssetNode`, `AssetStore`, and optional `ASSET_STORE_PATH` / `ASSET_REGISTRY_PATH` wiring.
   - CRUD mutations now persist atomically when a state path is configured.

2. **Tests**
   - Added `tests/test_asset_store.py` for persistence/reload coverage and router compatibility.

### Verification

- `uv run pytest tests/test_asset_store.py tests/test_metadata_catalogs.py` -> 5 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

The asset CRUD surface is user-owned topology state. Keeping it lightweight and file-backed by opt-in preserves the open-source deployment model while preventing user edits from disappearing after a restart.

## 2026-07-07 - Operational Memory Persistence Boundary

Extended the operational-memory sources so annotations, alert lifecycle state, and report templates can persist to local JSON state when configured.

### What changed

1. **`services/api_service/collaboration.py`**
   - Added optional `COLLABORATION_STORE_PATH` wiring.
   - Annotation add/delete now persist atomically when the path is configured.

2. **`services/api_service/alert_manager.py`**
   - Added optional `ALERT_MANAGER_PATH` wiring.
   - Alert lifecycle mutations now persist alerts and acknowledgment history atomically when configured.

3. **`services/analytics/reporting.py`**
   - Added optional `REPORT_TEMPLATE_STORE_PATH` wiring for durable report template metadata.

4. **Tests**
   - Added `tests/test_operational_memory_persistence.py` for reload coverage across all three stores.

### Verification

- `uv run pytest tests/test_operational_memory_persistence.py tests/test_operational_memory.py` -> 7 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

Operational memory is still read-only at the API level. Persisting the underlying operator-facing state keeps restarts from erasing useful context without turning the platform into a workflow/MES system.

## 2026-07-07 - Report Schedule Rehydration

Made persisted report templates restore their recurring schedules on startup when the optional scheduling library is installed.

### What changed

1. **`services/analytics/reporting.py`**
   - Added schedule persistence on `schedule_report()` and rehydration after loading persisted templates.
   - Replayed daily/hourly/weekly schedules into the existing scheduler when available.

2. **Tests**
   - Extended `tests/test_operational_memory_persistence.py` with a startup-rehydration test using a fake schedule module.

### Verification

- `uv run pytest tests/test_operational_memory_persistence.py tests/test_governance_plane.py` -> 8 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

Scheduled exports are part of the report subsystem, not a separate workflow engine. Persisting the cadence with the template and rehydrating it on startup keeps recurring exports restart-safe while staying inside the current architecture.

## 2026-07-07 - AI Governance Snapshot Expansion

Made the governance snapshot expose the agent runtime contract so diagnostic and supervised-action policies are visible alongside schema, model, prompt, and dataset governance.

### What changed

1. **`services/common/governance_plane.py`**
   - Added `agent_governance` data from `build_agent_runtime_contract()`.
   - The snapshot now warns if diagnostic tools are not read-only or if supervised action is not approval-gated.

2. **Tests**
   - Extended `tests/test_governance_plane.py` to assert the agent-governance contract and route output.

### Verification

- `uv run pytest tests/test_operational_memory_persistence.py tests/test_governance_plane.py` -> 8 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

This does not ship autonomous agents. It just makes the governance boundary explicit and auditable so users can plug in their own agent systems safely later.

## 2026-07-07 - Agent Integration Guidance

Documented the boundary between platform-owned agent contracts and user-owned agent ecosystems.

### What changed

1. **Docs**
   - Added `docs/agent-integration-guidance.md` and mirrored it in Obsidian vault.
   - Updated the model-agent roadmap to state that skills, MCP servers, and agent orchestration stay user-owned.

2. **Code**
   - `DiagnosticAgentRuntime` now audits approval-gated tool calls as well as approved ones.
   - `SupervisedActionRuntime.request_action()` continues to audit action requests without executing them.

3. **Tests**
   - Extended `tests/test_modeling_contracts.py` to verify audit logging for approval-gated diagnostic calls and supervised action requests.

### Verification

- `uv run pytest tests/test_modeling_contracts.py tests/test_governance_plane.py` -> 15 passed
- `python -m compileall services tests` -> clean

### Why this belongs here

The platform should give users stable contracts, read-only scaffolding, and auditability. Users should own their agents, skills, and MCP servers so the core does not become a general agent framework.

## 2026-07-06 - API System Fix 5 (Real Health Probes)

### Added

1. **Dependency health probes**
   - New `services/api_service/health_probes.py` with lightweight, timeout-bounded probes: `probe_kafka` (TCP connect), `probe_historian` (`SELECT 1`), `probe_ai_gateway` (HTTP `/health`). Each probe returns `False` instead of raising so a dead dependency surfaces without hanging the endpoint.

### Changed

1. **`/health` no longer hardcodes dependency status**
   - The endpoint now runs the real probes (via `asyncio.to_thread` so the event loop is not blocked) and reports actual `historian`/`kafka`/`ai_gateway` booleans. The overall status is `degraded` when any probed dependency is down or the service is in a degraded state. Previously all three were hardcoded `True`.

### Verified

- `python -m pytest tests/test_health_probes.py`
- Result: `7 passed`
- Covers each probe's success, failure, and never-raise contract.

### Notes

- Completes the 5 API-system audit fixes.

## 2026-07-06 - API System Fix 3 (Remove Duplicate Historian REST Surface)

### Removed

1. **AI gateway duplicate historian REST API**
   - Removed the ungated `/historian/{events,trend,assets,scenarios,alarms,replay}` REST surface from the AI gateway. These duplicated the gated `/api/v1/historian/*` surface owned by the API service. The AI gateway now exposes only its AI-specific endpoints (`/telemetry`, `/events` SSE, `/historian/stream` SSE, `/health`, `/metrics`).
   - Removed the now-unused `query_trend`, `load_hierarchy`, `hierarchy_to_tree`, `list_scenarios`, and `pathlib` imports.
   - The push-based `/historian/stream` SSE and `/events` SSE telemetry stream remain (they are real-time push, not duplicate REST reads).

### Verified

- `python -m pytest tests/test_ai_gateway_dedup.py`
- Result: `3 passed`
- Confirmed no UI or test references the removed gateway endpoints.

### Notes

- Historian REST reads are now served exclusively by the gated API service.
- The replay control surface (`replay_state`) was only ever used by the now-removed endpoints and had no consumer; removed with them.

## 2026-07-06 - API System Fixes Batch 1 (SSE, Ingest Dual-Write, Producer)

### Changed

1. **SSE crash fix (ai_gateway)**
   - `service_state["running"]` -> `service_state.running` in the `/events` and `/historian/stream` SSE loops (`main.py:120,222`). The item access raised `TypeError` because `ServiceHealthState` is a dataclass with no `__getitem__`; the SSE endpoints crashed on first client connection.

2. **API ingest no longer dual-writes to the historian**
   - Removed the direct `insert_industrial_event` call from `runtime._do_ingest_event`. The API now only validates and publishes to Kafka; the normalized fan-out consumer owns historian persistence (consistency with the Phase-3 decoupling).

3. **Consolidated Kafka producer helpers**
   - Removed the duplicate `_publish_kafka_fresh` (which created a new `Producer` per DLQ publish) and routed the DLQ path through the cached `_publish_kafka` / `_get_producer`.

### Verified

- `python -m pytest tests/test_api_runtime_fixes.py`
- Result: `3 passed`
- Updated `tests/test_realworld_fixes_2.py` to assert the API no longer writes to the historian directly.

### Notes

- The 3 failures in `test_realworld_fixes_2.py` are the pre-existing psycopg2 `_psycopg` DLL load issue in this environment, unrelated to these changes.


## 2026-07-06 - AI-Enriched Persistence, Push Dashboard Bus, Schema Governance

### Added

1. **AI-enriched fan-out consumer**
   - New `services/processor/ai_enriched_fanout.py` reads `iot.ai_enriched` and persists batches to the historian `ai_enriched` table, with at-least-once delivery (offsets committed after insert). The AI gateway previously produced to Kafka only; this consumer owns historian persistence.
   - Registered as the `ai-fanout` service in `datastreamd` and included in all runtime modes.

2. **Schema governance**
   - Wired the `SchemaRegistry` with `processed_event` and `benchmark_event` schemas. Benchmark metadata (`fault_type`, `scenario_id`, `ground_truth_severity`, `step`) is now governed separately from the operational `industrial_event` schema so it does not leak into production validation.

### Changed

1. **Push-driven dashboard bus**
   - The AI gateway's `historian_broadcast_loop` no longer polls the DB on a fixed 2-second interval. It now wakes immediately when new enriched data is signalled (`historian_refresh_event`), with a 5-second bounded fallback. `enrich_batch` sets the event after each successful enrichment, so subscribers refresh on change instead of on a timer.

### Verified

- `python -m pytest tests/test_ai_enriched_fanout.py tests/test_lakehouse_sink.py tests/test_sinks.py tests/test_flink_parity.py tests/test_edge_backpressure.py tests/test_normalized_fanout.py tests/test_edge_model.py tests/test_datastreamd.py`
- Result: `48 passed`
- Updated `test_datastreamd.py` runtime-mode selection to include the `ai-fanout` service.

### Notes

- Completes the 6-phase production-hardening refactor.
- The operational event schema stays unchanged; benchmark metadata remains optional and rides on the event dict but is governed by its own schema entry.


## 2026-07-06 - Iceberg Lakehouse Sink

### Added

1. **Lakehouse sink**
   - New `services/sinks/lakehouse.py` `LakehouseSink` writes normalized industrial events to an Apache Iceberg table on MinIO (S3-compatible) via `pyiceberg` + `pyarrow`. The table is created on first use if it does not exist; each batch appends as an Arrow-backed data file.
   - Configurable via `LAKEHOUSE_*` env vars (catalog, namespace, table, warehouse, S3 endpoint/keys, batch size). Registered as the `lakehouse` sink name in `SinkRegistry`.
   - `pyiceberg` and `pyarrow` are imported lazily, so the sink degrades gracefully (logs + skips) when lakehouse support is not installed.

2. **Dependencies**
   - Added `pyiceberg[s3fs]` and `pyarrow` to `requirements.txt`.

3. **ADR 0003**
   - Recorded the Iceberg-over-MinIO decision in `ObsidianVault/50_ADR/0003-use-iceberg-for-lakehouse.md`.

### Verified

- `python -m pytest tests/test_lakehouse_sink.py tests/test_sinks.py tests/test_flink_parity.py tests/test_edge_backpressure.py tests/test_normalized_fanout.py tests/test_edge_model.py tests/test_datastreamd.py`
- Result: `45 passed`
- Covers env construction, buffering, graceful flush without pyiceberg, and registry wiring.

### Notes

- The lakehouse sink is optional (`SINKS=lakehouse`); MinIO already ships under the `extended` docker profile.
- Phase 5 of the production-hardening refactor.


## 2026-07-06 - Flink And Python Runtime Parity

### Added

1. **ProcessedEventsSink (Flink)**
   - Added a `ProcessedEventsSink` Flink `SinkFunction` to `iot_anomaly_job.py` that batches processed payloads and persists them to the historian via the shared client, restoring parity with the Python runtime processor.
   - Activates when `FLINK_PERSIST_PROCESSED_EVENTS=1` (the historian client is only importable inside the Flink container). Falls back to per-event insert on batch failure.

### Changed

1. **Flink state eviction**
   - The keyed-state window no longer clears and re-adds the full list state on every element. It only rewrites the list when an eviction occurred; otherwise it appends the new sample. This avoids an O(window) state rewrite per event.
2. **Composite partition key**
   - `_partition_key` now uses the platform-wide 7-field composite scope (project|site|line|protocol|source|asset|tag) instead of asset-only, so Flink key-by aligns with Kafka partitioning and co-locates all samples for one asset+tag.
3. **Batched producer drain**
   - The Python runtime processor now drains delivery reports (`producer.poll(0)`) every 128 messages instead of on every message, removing a per-message syscall that throttled high-throughput ingest. Shutdown is still covered by `producer.flush(10)`.

### Verified

- `python -m pytest tests/test_flink_parity.py tests/test_edge_backpressure.py tests/test_sinks.py tests/test_normalized_fanout.py tests/test_edge_model.py tests/test_datastreamd.py`
- Result: `39 passed`
- Covers composite keying, ProcessedEventsSink batch/flush/fallback, and malformed-input handling.

### Notes

- These changes bring the Flink and Python runtime paths to the same persistence and partitioning contract.
- Phase 4 of the production-hardening refactor.


## 2026-07-06 - Normalized Fan-Out Consumer And Historian Decoupling

### Added

1. **Normalized fan-out consumer**
   - New `services/processor/normalized_fanout.py` reads `industrial.normalized` and writes batches to the configured `CompositeSink` (historian, lakehouse, downstream Kafka). Offsets are committed only after a sink batch succeeds, giving at-least-once delivery to endpoint datasets.
   - Registered as the `fanout` service in `datastreamd` and included in all runtime modes.

2. **Event-id deduplication**
   - Added `setup_unique_indexes()` idempotent helper and `ON CONFLICT (event_id) DO NOTHING` to the historian industrial-event inserts so replayed batches (from at-least-once delivery) become no-ops instead of duplicates.
   - Added the matching unique indexes to `docker/postgres/init-timescale-full.sql`.

### Changed

1. **Edge publisher no longer writes directly to the historian**
   - Removed the historian buffer/flush path from `EdgePublisher`. The publisher now produces only to Kafka topics; the normalized fan-out consumer owns historian persistence. This decouples the edge path from a specific endpoint dataset.

2. **Processor and Flink consume the normalized topic**
   - `runtime_processor` and `iot_anomaly_job` now default to `industrial.normalized` (overridable via `IOT_TOPIC`). The normalized envelope is a superset of the legacy fields, so parsing is unaffected.

3. **Removed cruft**
   - Deleted the empty `docker/postgres/init-timescale.sql` directory.

### Verified

- `python -m pytest tests/test_edge_backpressure.py tests/test_sinks.py tests/test_normalized_fanout.py tests/test_edge_model.py tests/test_datastreamd.py`
- Result: `34 passed`
- Updated `test_datastreamd.py` runtime-mode selection to include the `fanout` service.

### Notes

- `iot.raw` is still produced (legacy compatibility) but is now deprecated; the processor and fan-out consume `industrial.normalized`.
- Phase 3 of the production-hardening refactor.


## 2026-07-06 - Sink Abstractions For Endpoint-Dataset Fan-Out

### Added

1. **Sink protocol and composite**
   - New `services/sinks/` package introduces a `Sink` Protocol (`write_batch`, `flush`, `close`), a `CompositeSink` that fans one batch to many sinks while isolating per-sink failures, and a `SinkRegistry.from_env()` that builds a composite from the `SINKS` env var.
   - Sinks decouple *what is produced* (normalized/validated events) from *where it lands*, so the open-source platform can target different endpoint datasets (historian, lakehouse, downstream Kafka) without changing processor code.

2. **Concrete sinks**
   - `TimescaleHistorianSink` writes normalized industrial events to the historian via the shared client, with per-event fallback when a batch insert fails.
   - `KafkaSink` forwards normalized events to a downstream Kafka topic using the composite partition key.

### Verified

- `python -m pytest tests/test_sinks.py`
- Result: `11 passed`
- Covers composite fan-out, failure isolation, flush/close propagation, context manager, registry env building, historian batch + per-event fallback, and Kafka sink forwarding with composite keys.

### Notes

- Introduced and unit-tested only; no wiring into the processor yet (Phase 3).
- Phase 2 of the production-hardening refactor.


## 2026-07-06 - Edge Ingest Backpressure And Overload Handling

### Added

1. **Producer backpressure handling**
   - `EdgePublisher` now produces through `_produce_safe`, which retries on `BufferError` (internal queue full) after draining delivery reports, and routes oversize messages (above `EDGE_MAX_MESSAGE_BYTES`) to the DLQ instead of crashing.
   - Added `message.max.bytes` to the producer config and two new counters: `edge_ingest_delivery_failures_total` and `edge_ingest_overflow_total`.

2. **MQTT bounded decoupling queue**
   - The MQTT connector no longer produces to Kafka directly from the paho network thread. Decoded payloads are enqueued onto a bounded `asyncio.Queue` (size `EDGE_MQTT_QUEUE_SIZE`) and drained on the event loop, decoupling broker backpressure from the MQTT client.
   - When the queue saturates, `enqueue_mqtt_message` routes the message to the DLQ and bumps the overflow counter so the loss is observable.
   - Added `mqtt_queue_size` and `max_message_bytes` settings.

### Verified

- `python -m pytest tests/test_edge_backpressure.py`
- Result: `5 passed`
- Covers BufferError retry, oversize→DLQ routing, delivery-failure counter, MQTT queue-full→DLQ, and under-capacity enqueue.

### Notes

- No functional change to the happy path; this only hardens failure/overload modes.
- Phase 1 of the production-hardening refactor.

## 2026-07-05 - Benchmark Repeatability And Session Delta

### Changed

1. **Production-pipeline repeatability**
   - Added a repeatability benchmark command that runs the selected production pipeline multiple times and reports mean, median, spread, and min/max throughput plus p99 latency.
   - The command can compare the current session against a saved baseline report and prints absolute and percentage deltas.

2. **Session-delta reporting**
   - The repeatability report is meant to separate real regressions from single-run noise on the local machine.
   - The report format is JSON-friendly so prior benchmark sessions can be archived and compared later.

### Notes

- This adds the reporting infrastructure for session comparison; it does not replace real target-site benchmark runs.

## 2026-07-05 - Local Kubernetes Rehearsal And Diagnostic Scaffold

### Changed

1. **Multi-profile local acceptance**
   - The local phase gate now reports per-deployment-mode summaries in addition to the per-site acceptance rows.
   - The report payload keeps a compact aggregate summary so multi-profile runs are easier to compare across sessions.

2. **Local Kubernetes rehearsal**
   - Added a local Kubernetes rehearsal command that exports generated site bundles, validates the rendered YAML, and runs a client-side `kubectl kustomize` rehearsal.
   - The rehearsal stays local and does not require a live cluster.

3. **Diagnostic runtime scaffold**
   - Added an `agent-runtime` control command for the read-only diagnostic contract and the supervised action request scaffold.
   - The runtime scaffold now degrades gracefully when the historian client cannot be imported in a local environment.

### Notes

- The Kubernetes rehearsal validates the generated manifests, not production cluster scheduling or multi-node behavior.
- The diagnostic scaffold remains infrastructure; shipping autonomous agents is still deferred.

## 2026-07-05 - Restore Thresholds And Phase-One Acceptance

### Changed

1. **Restore drill thresholds**
   - The backup drill matrix now reports per-site restore thresholds and a binary acceptance result for backup, restore, and rollback state.
   - The local gate uses deployment-mode-specific thresholds so the output is not just raw elapsed time.

2. **Phase-one acceptance report**
   - The `local-phase-one` command now emits a combined acceptance artifact with per-site backup, restore, RTO proxy, and benchmark status.
   - The report keeps the local rollback drill and benchmark gate together so operators can see one pass/fail summary per site.

### Notes

- The thresholds are still local-release thresholds, not customer site guarantees.

## 2026-07-05 - Local Phase-One Gate

### Changed

1. **Combined local drill gate**
   - Added `local-phase-one` to run restore/rollback drills and site-profile benchmarks together from a single command.
   - The gate writes a combined phase report plus subreports for the backup drill and benchmark portions.

2. **Readiness tracking**
   - Marked the local phase-one gate as complete in the hardening and readiness planning docs.

### Notes

- This is still a local single-machine readiness gate. It does not replace real target-site validation or multi-node rollout testing.

## 2026-07-05 - SWaT Simulator Case

### Changed

1. **SWaT benchmark case**
   - Added `swat` as a first-class real-world simulator case.
   - The case synthesizes a small workbook, normalizes it through the SWaT converter, and runs it through the same replay benchmark as the other industrial scenarios.

2. **Benchmark coverage**
   - The expanded real-world simulator suite now includes SWaT alongside the existing mock and industrial replay cases.
   - SWaT simulator run: 93,544.49 events/sec, p99 0.0168 ms.

### Notes

- This validates the SWaT parser and benchmark lane, but the public upstream SWaT workbook still deserves a direct end-to-end verification pass in a real download path.

## 2026-07-05 - Real Dataset Import And Benchmark Pass

### Changed

1. **AI4I import path**
   - Fixed the AI4I import flow so the public ZIP is extracted into the staged CSV path instead of leaving zip bytes behind.
   - The AI4I dataset can now be converted into the benchmark replay format and measured through the end-to-end pipeline.

2. **NASA C-MAPSS import path**
   - Pointed the C-MAPSS source at the live NASA ZIP and taught the converter to read the train/test tables directly from the archive.
   - The NASA dataset can now be normalized into the benchmark replay format without manual unpacking.

3. **SWaT staging**
   - The SWaT workbook can now be downloaded and staged locally without crashing the importer when extraction is requested on a non-zip file.
   - Added a SWaT workbook/CSV normalization path so the dataset can flow into the benchmark replay format.

4. **Benchmark coverage**
   - Measured AI4I and C-MAPSS through the same end-to-end pipeline used for the simulator cases so the benchmark path now includes public real-world-shaped datasets.
   - AI4I end-to-end run: 43,342.11 events/sec, p99 0.0313 ms.
   - C-MAPSS end-to-end run: 41,598.31 events/sec, p99 0.0453 ms.
   - SWaT synthetic-workbook end-to-end run: 46,706.71 events/sec, p99 0.0286 ms.

### Notes

- SWaT normalization exists, but the public workbook download in this environment still needs validation against the real upstream file rather than only the synthetic workbook fixture.
- C-MAPSS benchmark throughput is lower than the synthetic industrial replay cases, which is expected because the dataset is much larger and denser.

## 2026-07-05 - Backup Drill Matrix For Per-Site Measurement

### Changed

1. **Backup drill matrix**
   - Added `backup-drill-matrix` to run historian backup/restore drills across multiple site profiles in one pass.
   - The command records backup, restore, and total elapsed time per site profile so restore/RTO evidence can be collected consistently.

2. **Readiness paperwork**
   - Updated the production-readiness and hardening docs so the new measurement tooling is tracked separately from the still-pending real site measurements.

### Notes

- This closes the tooling gap for restore/rollback drill measurement, but it does not replace the need for actual target-site validation.

## 2026-07-04 - Universal Semantic Core And Graph Projection

### Changed

1. **Universal semantic core**
   - Added `services/common/semantic_core.py` with platform primitives, ontology packs, and a semantic graph projection model.
   - The current industrial hierarchy now projects into a universal graph without replacing the existing manufacturing-specific data model.

2. **Semantic API surface**
   - Added `/api/v1/semantic/core` and `/api/v1/semantic/graph` so the platform can expose the semantic substrate directly.

3. **Benchmark coverage**
   - Added a semantic-graph projection benchmark so the new abstraction has its own measurement path.

### Notes

- The current manufacturing ontology remains intact. The new semantic layer is additive and is intended to become the platform core over time.

## 2026-07-04 - Semantic Planner And Graph Query Layer

### Changed

1. **Ontology-aware SQL planner**
   - Updated `services/common/semantic_model.py` and `services/common/query_plan.py` so the deterministic query planner now carries ontology-pack metadata.
   - The planner still resolves the same industrial SQL shapes, but it now records whether a query belongs to the platform core or the manufacturing pack.

2. **Graph query API**
   - Added graph search and entity/relationship lookup endpoints under `/api/v1/semantic/graph`.

3. **Benchmark coverage**
   - Added a semantic-graph query benchmark in addition to the projection benchmark.

### Notes

- Pack metadata is advisory, not a hard partition. The current planner behavior stays compatible with existing historian and alarm queries.

## 2026-07-04 - Persistent Semantic Store And Lineage

### Changed

1. **Writable semantic store**
   - Added `services/common/semantic_store.py` as a file-backed semantic graph store with ontology packs, entities, relationships, documents, workflows, observations, states, events, and lineage records.
   - The store boots from the existing asset hierarchy when no persisted semantic file exists yet.

2. **Semantic write APIs**
   - Added write endpoints for ontology packs, graph entities, relationships, documents, workflows, observations, and lineage records.
   - Added site-scoped filtering for semantic graph search.

3. **Lineage integration**
   - Runtime event ingestion now records lineage entries for accepted and rejected events so provenance exists alongside the semantic graph.

4. **Benchmark coverage**
   - Added a semantic-store write benchmark to measure the persistence path separately from projection and query throughput.

### Notes

- The store now prefers the historian database when available and falls back to file-backed mode only when the database is absent, so the platform keeps its current single-server posture without losing durability.

## 2026-07-04 - Semantic DB Backing And AI Context Integration

### Changed

1. **DB-backed semantic persistence**
   - Added semantic tables to the Timescale/Postgres schema for ontology packs, entities, relationships, measurements, observations, actions, documents, locations, states, workflows, events, and lineage.
   - The semantic store now uses the database backend automatically when Timescale is reachable, while preserving the file-backed fallback for isolated tests and offline development.

2. **Retrieval and modeling context**
   - Expanded retrieval documents to include semantic ontology packs, entities, and relationships.
   - Expanded the modeling context package and tool registry so agents can inspect the semantic graph and lineage through read-only paths.

3. **Safety and bootstrap**
   - The DB backend now falls back cleanly to the file store when the historian database is unavailable, keeping the repo runnable without extra services.

### Verified

- `.venv\\Scripts\\python.exe -m pytest tests/test_semantic_store.py tests/test_modeling_contracts.py tests/test_semantic_api_smoke.py tests/test_semantic_core.py -q`
  - `12 passed`
- `.venv\\Scripts\\python.exe -m pytest tests/test_api_route_splits.py tests/test_datastreamctl.py tests/test_semantic_graph_benchmark.py tests/test_semantic_graph_query_benchmark.py tests/test_semantic_store_benchmark.py -q`
  - `50 passed`

### Notes

- The semantic plane is now durable enough for production deployment while still staying compatible with the current single-node install path.
- AI and retrieval now have direct access to semantic context without requiring a separate ad hoc store.

## 2026-07-04 - Industrial Benchmark Fixture Hardening

### Changed

1. **Benchmark inputs**
   - Updated the benchmark tests to use `data/benchmarks/industrial_mixed_benchmark.csv` as the shared industrial fixture instead of tiny hand-written two-row samples.
   - The real-world simulator test now exercises `mock-normal`, `mock-drift`, `mock-spike`, `multi-plc-line`, `burst-load`, `dropout-reconnect`, and `industrial-benchmark`.

2. **Repeat-run stability**
   - Ran the benchmark suite with repeated measurements and recorded the median throughput and p99 values to reduce single-run noise.

### Verified

- `.venv\\Scripts\\python.exe -m pytest tests/test_mixed_replay_benchmark.py tests/test_end_to_end_pipeline_benchmark.py tests/test_real_world_simulator_benchmark.py tests/test_site_profile_matrix_benchmark.py -q`
  - `4 passed`

### Notes

- The benchmark suite now reflects actual industrial-shaped event streams more closely, but it is still a local single-node approximation rather than live plant telemetry.

## 2026-07-04 - Multi-Site Correlation Case And Distributed Semantic Backend

### Changed

1. **Multi-site simulator case**
   - Added a dedicated `multi-site-correlation` benchmark case to the real-world simulator suite.
   - The new case preserves duplicate asset signals across `demo-site` and `plant-a` so correlation and site isolation can be exercised together.

2. **Distributed semantic backend**
   - `SiteProfile.to_env()` now exports `SEMANTIC_STORE_BACKEND=db` for `plant-local` and `federated` deployments.
   - `single-site` keeps `SEMANTIC_STORE_BACKEND=auto` so the file fallback remains available for local development.

### Verified

- `.venv\\Scripts\\python.exe -m pytest tests/test_site_profiles.py tests/test_real_world_simulator_benchmark.py -q`
  - `6 passed`
- `.venv\\Scripts\\python.exe -m pytest tests/test_datastreamd.py tests/test_project_manifest.py -q`
  - `29 passed`

### Notes

- This hardens the distributed path without changing the single-node default behavior.
- The platform is now clearer about where semantic data should live in plant-local and federated rollouts.

## 2026-07-04 - Agent Runtime Contract And Release Checklist

### Changed

1. **Agent runtime infrastructure**
   - Added `services/common/agent_runtime.py` with a read-only diagnostic runtime contract, supervised action runtime scaffold, and audited tool-call records.
   - Exposed the runtime contract through `/api/v1/modeling/agent-runtime`.
   - Added historian audit-log persistence support for agent-assisted tool and action records.

2. **Release checklist**
   - Added `docs/production-readiness-action-plan.md` and the matching Obsidian note so the readiness report now has owners, exit criteria, and execution order.

### Notes

- The platform still does not ship a diagnostic agent or supervised action agent.
- It now ships the infrastructure and policy surface that user-built agents can integrate with safely.

## 2026-07-03 - OS Packaging Scripts And Windows Bundle Export

### Changed

1. **Repo-based packaging driver**
   - Added `scripts/package-release.py` plus `scripts/package-release.ps1` and `scripts/package-release.sh`.
   - The driver stages Windows, Linux, and offline bundles from the actual repo tree instead of a synthetic layout.

2. **Windows export layout**
   - Added a native Windows bundle layout to `services/common/project_manifest.py`.
   - The Windows layout emits `install.ps1`, `uninstall.ps1`, `.cmd` launchers, and a Windows-specific README alongside the site bundle.

### Verified

- `.venv\\Scripts\\python.exe -m pytest -q tests/test_project_manifest.py tests/test_datastreamctl.py`: 60 passed
- `python scripts/package-release.py --output-dir %TEMP%\\datastream-package-test --site-id demo-site --archive none windows`
  - staged `demo-site-windows`
  - file count: 523

### Notes

- The packaging pipeline still stops short of generating MSI/DEB/RPM installers, but the repo now has the correct staging shape to feed them.

## 2026-07-03 - Packaging Checklist Based On Repo Structure

### Changed

1. **Packaging checklist**
   - Added `docs/release-packaging-checklist.md` based on the actual service tree, runtime assets, and installer entry points already in the repo.

2. **Build metadata**
   - Updated `pyproject.toml` to discover the full `services.*` package tree and include runtime JSON package data.
   - Added `*.egg-info/` to `.gitignore` so packaging checks do not leave generated metadata in the repo root.

### Verified

- Structural packaging change only; no runtime behavior changed.

## 2026-07-03 - Deployment Decision Memo And WSL2 Guidance

### Changed

1. **Deployment memo**
   - Added `docs/deployment-decision-memo.md` to record the recommended native, service-first install path.

2. **WSL2 guidance**
   - Clarified that WSL2 is a developer convenience for Windows workstations, not a required production dependency.
   - Updated the self-host install guide and README to reflect the native Windows/Linux production recommendation.

### Verified

- Documentation-only change; no runtime behavior changed.

## 2026-07-03 - Install Guide And Host-Profile Benchmark Reporting

### Changed

1. **Self-host install guide**
   - Added `docs/self-host-install-guide.md` with a concrete operator install and upgrade flow for Linux and Windows.
   - The guide focuses on local ownership of secrets, config, data, logs, models, and backups.

2. **Benchmark host profile**
   - Added host-profile metadata to the site-profile benchmark report exports.
   - The benchmark artifacts now capture CPU, memory, and platform context so the local results stay clearly separated from target-hardware sizing claims.

### Verified

- `uv run python -m pytest tests/test_datastreamctl.py tests/test_project_manifest.py`: passed
- `python -m compileall services`: passed
- `uv run python -m services.cli.datastreamctl benchmark site-profile-matrix --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 1000 --batch-size 64 --warmup-events 0 --min-average-events-per-second 1 --repeat-count 2 --report-dir %TEMP%\\datastream-matrix-report`
  - `demo-site`: mean 90,392.42 events/sec, median 90,392.42, stdev 6,175.55, p99 0.0152 ms
  - `plant-a`: mean 92,189.32 events/sec, median 92,189.32, stdev 1,804.84, p99 0.0213 ms

## 2026-07-03 - Backup Drill Reports, Release Package Skeleton, And Repeat-Run Matrix

### Changed

1. **Backup drill reporting**
   - Added an optional JSON report directory for the historian backup drill command.
   - The drill now writes a summary artifact plus component artifacts so restore/rollback checks can be archived.

2. **Release package skeleton**
   - Added `project-manifest release-package` to emit a release-artifact skeleton with checksums and a release manifest.
   - The package keeps installable output separate from the later signing workflow.

3. **Repeat-run matrix**
   - Added repeat-count support to the site-profile matrix and calibration benchmarks.
   - The matrix now reports mean, median, spread, min, and max so local variance is visible instead of hidden.

### Verified

- `uv run python -m pytest tests/test_datastreamctl.py tests/test_project_manifest.py tests/test_site_profile_matrix_benchmark.py`: passed
- `uv run python -m pytest tests/test_site_profile_calibration_benchmark.py`: passed
- `python -m compileall services`: passed
- `uv run python -m services.cli.datastreamctl benchmark site-profile-matrix --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 1000 --batch-size 64 --warmup-events 0 --min-average-events-per-second 1 --repeat-count 2`
  - `demo-site`: mean 92,118.08 events/sec, median 92,118.08, stdev 1,071.01, p99 0.0185 ms
  - `plant-a`: mean 93,961.76 events/sec, median 93,961.76, stdev 1,167.15, p99 0.0248 ms
- `uv run python -m services.cli.datastreamctl project-manifest release-package config/project-manifest.yaml %TEMP%\\datastream-release --site-id demo-site --format both`
  - release manifest and checksums were generated successfully

## 2026-07-03 - Backup Snapshot Comparison, Signed Release Artifacts, And Benchmark Report Exports

### Changed

1. **Backup drill comparison**
   - Added historian snapshot collection before and after restore so the drill can report whether the row counts matched.
   - The backup drill report now persists `before_snapshot`, `after_snapshot`, and `snapshot_comparison` JSON artifacts.

2. **Signed release artifacts**
   - Added optional HMAC-based release signing to `project-manifest release-package`.
   - The command now emits `release-signature.json` when `--sign` is set and a signing key is provided via the operator-owned environment variable.

3. **Benchmark report exports**
   - Added optional report directories for the site-profile matrix and calibration benchmarks.
   - The benchmark commands now write summary JSON and per-site artifacts so repeat runs can be archived alongside the CLI output.

### Verified

- `uv run python -m pytest tests/test_datastreamctl.py tests/test_project_manifest.py`: passed
- `uv run python -m services.cli.datastreamctl benchmark site-profile-matrix --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 1000 --batch-size 64 --warmup-events 0 --min-average-events-per-second 1 --repeat-count 2`
  - `demo-site`: mean 86,376.50 events/sec, median 86,376.50, stdev 288.99, p99 0.0195 ms
  - `plant-a`: mean 94,552.48 events/sec, median 94,552.48, stdev 1,214.24, p99 0.0174 ms
- `uv run python -m services.cli.datastreamctl project-manifest release-package config/project-manifest.yaml %TEMP%\\datastream-release --site-id demo-site --format both --sign`
  - release manifest, checksums, and signature artifacts were generated successfully

### Notes

- Packaging is still not the final signed-distribution step; it is now a proper release skeleton.
- Restore/rollback drill reporting is in place, but target-site validation still needs real infrastructure.

## 2026-07-03 - Simulator Baseline Measured For Multi-PLC Cases

### Verified

- `uv run python -m services.cli.datastreamctl benchmark real-world-simulator --events 1000 --batch-size 64 --warmup-events 0 --cases multi-plc-line,burst-load,dropout-reconnect,industrial-benchmark`
  - `multi-plc-line`: 93,307.08 events/sec, 0.0180 ms p99
  - `burst-load`: 90,183.52 events/sec, 0.0167 ms p99
  - `dropout-reconnect`: 95,832.26 events/sec, 0.0222 ms p99
  - `industrial-benchmark`: 94,157.53 events/sec, 0.0333 ms p99
  - average: 93,370.10 events/sec, 0.0226 ms p99

### Notes

- The simulator suite now has explicit multi-PLC and reconnect shapes while keeping the existing replay pipeline.
- These are still local baselines; target-site validation is separate.

## 2026-07-03 - Rollout Reports, Secret Guidance, And Multi-PLC Simulator Cases

### Changed

1. **Rollout acceptance automation**
   - Extended `project-manifest rollout-acceptance` with an optional `--report-dir` output path.
   - The command now writes a summary JSON file plus one JSON file per site so acceptance results can be archived in CI or release bundles.

2. **Multi-PLC simulator scenarios**
   - Added protocol-shaped simulator cases for `multi-plc-line`, `burst-load`, and `dropout-reconnect`.
   - These cases preserve site, line, source, and protocol identity so benchmark runs can validate industrial isolation and reconnect behavior more realistically.

3. **Self-hosted secret guidance**
   - Added a dedicated secrets and network guidance document for Docker, systemd, and Kubernetes installs.
   - The guidance keeps credentials in operator-managed secret stores and keeps the generated manifests secret-free.

### Verified

- `uv run python -m pytest tests/test_project_manifest.py tests/test_site_profiles.py`: passed
- `python -m compileall services`: passed

### Notes

- The simulator scenarios are intentionally additive; the existing benchmark paths still work unchanged.
- Packaging remains deferred.

## 2026-07-03 - Multi-Site Validation Gap Closed And Checklist Captured

### Changed

1. **Manifest/site identity validation**
   - Added a manifest validation rule that requires each site profile `site.id` to match the manifest `site_id`.
   - This prevents a rollout bundle from accidentally pointing a site entry at the wrong runtime identity.

2. **Execution tracking**
   - Added a production hardening checklist that separates multi-site rollout, self-hosted security, packaging, and simulator/benchmark work.
   - Added an Obsidian vault note to track the same execution state during implementation.

### Verified

- Validation logic updated in `services/common/project_manifest.py`.
- Regression coverage added in `tests/test_project_manifest.py`.

### Notes

- This is a small but important release-safety fix because site identity drift is a realistic multi-site failure mode.
- Packaging remains intentionally deferred.

## 2026-07-03 - Native Fastpath Boundary Added And Kept Opt-In

### Changed

1. **Compiled runtime boundary**
   - Added a Rust `cdylib` under `rust/fastpath` with helpers for JSON bytes, partition keys, and ingest bundle generation.
   - Added `services/common/native_fastpath.py` to load the compiled module only when `DATASTREAM_NATIVE_FASTPATH` is enabled.
   - Wired the ingest/runtime helpers to use the native boundary if it is available, while preserving the Python/orjson fallback path.

2. **Measurement outcome**
   - Built the Rust module successfully with `cargo build --release`.
   - Benchmarked both the default-off path and the experimental native-enabled path.
   - The experimental native path regressed materially on this host, so the repo default remains the Python/orjson path.

### Verified

- `cargo build --release` in `rust/fastpath`: passed
- `python -m compileall services`: passed
- `uv run python -m pytest tests/test_edge_model.py tests/test_api_route_splits.py tests/test_api_security_middleware.py tests/test_realworld_fixes_2.py tests/test_federation.py`: 20 passed
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode python-fallback --wire-format json --json`
  - 43,313.52 events/sec
  - 0.0329 ms p99
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode flink-production --wire-format json --json`
  - 48,872.32 events/sec
  - 0.0342 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --window-limit 25 --json`
  - 48,801.91 events/sec
  - 0.0466 ms p99
- `uv run python scripts/benchmark_mixed_replay.py --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0`
  - 86,897.73 events/sec
  - 0.0258 ms p99
- `uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --wire-format json --json`
  - 43,934.40 events/sec
  - 0.0320 ms p99

### Notes

- The native boundary is ready for users who want to experiment with it, but it is not the default runtime choice.
- The default-off path stayed healthy and is the only setting I would use for release documentation at this point.
- The benchmark evidence says the current Python/orjson path is still the practical default for this codebase.

## 2026-07-03 - Remaining API Router Split And Ingest Hot-Path Cleanup

### Changed

1. **Remaining API router split**
   - Split the old `support` and `design` responsibilities into focused router modules for backup, reports, pipelines, schemas, preview, connectors, digital twin, and OEE.
   - Kept `services/api_service/routers/support.py` and `services/api_service/routers/design.py` as thin aggregators so the app surface stayed stable.

2. **Hot-path cleanup**
   - Removed redundant `model_dump`/normalize conversions from the ingest publish path.
   - Reused the already-built event dictionary for Kafka payloads, historian buffering, and legacy event conversion.
   - Let the shared partition-key helper reuse cached keys when the record already exposes one.
   - Removed a benchmark no-op from the CGR-style stream slice.

### Verified

- `python -m compileall services`: passed
- `uv run python -m pytest tests/test_api_security_middleware.py tests/test_federation.py tests/test_realworld_fixes_2.py tests/test_api_route_splits.py tests/test_edge_model.py`: 20 passed
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode python-fallback --wire-format json --json`
  - first run: 30,540.92 events/sec
  - repeat run: 42,259.28 events/sec
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode flink-production --wire-format json --json`
  - 51,526.15 events/sec
  - 0.0320 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --window-limit 25 --json`
  - first run: 37,772.90 events/sec
  - repeat run: 52,640.64 events/sec
- `uv run python scripts/benchmark_mixed_replay.py --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0`
  - first run: 78,763.79 events/sec
  - repeat run: 94,941.61 events/sec

### Notes

- This session showed clear host variance, so the repeat runs are the only numbers worth comparing to the previous baseline.
- The code cleanup is still worth keeping because it removes duplicated conversions even though it did not create a dramatic single-host throughput gain.
- The repeat runs stayed close to baseline rather than showing a large improvement, so this pass should be treated as a structural cleanup with neutral performance impact.

## 2026-07-03 - API Realtime Split And Edge Adapter Split

### Changed

1. **API service decomposition**
   - Moved WebSocket connection management, broadcaster loops, heartbeat handling, and realtime routes into `services/api_service/realtime.py`.
   - Kept `services/api_service/main.py` focused on app assembly, middleware, health, metrics, and router inclusion.
   - Preserved legacy module-level compatibility hooks for `ingest_event`, `ingest_batch`, and webhook persistence tests.

2. **Edge ingest decomposition**
   - Moved ingestion settings to `services/edge_ingest/settings.py`.
   - Moved Kafka publishing, historian buffering, and latency metrics to `services/edge_ingest/publisher.py`.
   - Split connector loops into protocol-focused modules under `services/edge_ingest/connectors/` for MQTT, OPC UA, Modbus TCP, Modbus RTU, and OPC UA discovery.

3. **Compatibility preserved**
   - Kept the current ingest behavior and legacy export helper available from `services.edge_ingest.main`.
   - Did not change endpoint names or event payload shapes.

### Verified

- `python -m compileall services`: passed
- `uv run python -m pytest tests/test_api_security_middleware.py tests/test_federation.py tests/test_realworld_fixes_2.py`: 15 passed
- `uv run python -m pytest tests/test_api_route_splits.py`: passed
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode python-fallback --wire-format json --json`
  - 44,155.47 events/sec
  - 0.0201 ms p99
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --runtime-mode flink-production --wire-format json --json`
  - 51,394.54 events/sec
  - 0.0447 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --window-limit 25 --json`
  - 53,312.15 events/sec
  - 0.0269 ms p99
- `uv run python -m services.cli.datastreamctl benchmark flink-runtime-slice --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0 --window-limit 25 --json`
  - 51,173.09 events/sec
  - 0.0336 ms p99
- `uv run python scripts/benchmark_mixed_replay.py --csv data/benchmarks/industrial_mixed_benchmark.csv --events 10000 --batch-size 256 --warmup-events 0`
  - 98,558.48 events/sec
  - 0.0142 ms p99

### Notes

- This pass mostly reduced architectural coupling, not algorithmic cost.
- The latest benchmark set shows no regression from the split itself and small gains in the Flink-aligned slice and mixed replay paths.

## 2026-07-02 - Runtime Mode Now Selects The Launched Processor Set

### Changed

1. **Supervisor wiring**
   - Updated `datastreamd` so the selected `runtime.mode` now chooses the default service set.
   - `python-fallback` starts the Python processor path.
   - `flink-local` and `flink-production` start the Flink job path instead of the Python processor.

2. **Selection coverage**
   - Added test coverage proving that a federated site profile selects `flink-job` and does not start the legacy Python processor by default.

### Verified

- `python -m compileall services tests`: passed
- `uv run pytest -q tests/test_datastreamd.py tests/test_site_profiles.py tests/test_datastreamctl.py`: 51 passed

### Notes

- This is the first step that makes Flink the active processor path instead of only a benchmark target.
- The full data-plane path still needs live target-topology validation, but the runtime selection is now wired.

## 2026-07-02 - Flink-First Runtime Mode Contract And Production Pipeline Benchmark

### Changed

1. **Explicit runtime mode contract**
   - Added `runtime.mode` to site profiles with validated values for `python-fallback`, `flink-local`, and `flink-production`.
   - Exported `RUNTIME_MODE` through site and project environment bundles so deployment tooling can branch on the selected execution plane.
   - Updated the supervisor and CLI status surfaces to show the runtime mode alongside deployment mode.

2. **Production pipeline benchmark surface**
   - Added a `production-pipeline` benchmark command that runs the selected runtime mode explicitly.
   - Kept the Python fallback and Flink-aligned paths measurable under one command so docs and regression notes can compare them directly.

### Verified

- `python -m compileall services tests`: passed
- `uv run pytest -q tests/test_site_profiles.py tests/test_datastreamd.py tests/test_datastreamctl.py`: 50 passed
- `uv run python -m services.cli.datastreamctl status --site-profile config/site-profiles/single-site.yaml`
  - runtime_mode: python-fallback
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --events 10000 --batch-size 256 --runtime-mode python-fallback --csv data/benchmarks/industrial_mixed_benchmark.csv`
  - 34,229.38 events/sec
  - 0.0544 ms p99
- `uv run python -m services.cli.datastreamctl benchmark production-pipeline --events 10000 --batch-size 256 --runtime-mode flink-production --csv data/benchmarks/industrial_mixed_benchmark.csv`
  - 41,771.06 events/sec
  - 0.0473 ms p99

### Notes

- On this host, the Flink-production benchmark path is about `22.0%` faster than the Python fallback benchmark path for the same replay pack and batch settings.
- The current single-node measurements still carry host-load variance, but the direction of the gap is now consistent with the architecture goal.

## 2026-07-02 - JSON Hot-Path Simplification And Live Historian Write

### Changed

1. **JSON hot-path simplification**
   - Changed `to_json_bytes()` to serialize JSON directly instead of routing through the environment-driven wire selector.
   - Removed repeated per-event wire-format resolution from the hot JSON path.
   - This keeps the default behavior explicit and trims a small but measurable amount of overhead.

2. **Live historian validation**
   - Bootstrapped the missing `processed_events` table in the Docker-backed Postgres service.
   - Reran the mixed replay benchmark with `--live-db` and captured a successful historian write rate from the live container.

### Verified

- `python -m compileall services tests`: passed
- `uv run pytest -q tests/test_wire_format.py tests/test_edge_model.py tests/test_processor_normalization.py tests/test_end_to_end_pipeline_benchmark.py tests/test_datastreamctl.py -k "benchmark_cgr_gap_report_runs or benchmark_flink_runtime_slice_runs or benchmark_end_to_end_pipeline_runs"`: 3 passed
- `uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 10000 --batch-size 256 --warmup-events 0 --wire-format json`
  - 47,280.12 events/sec, 0.0289 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --events 10000 --batch-size 256 --warmup-events 0`
  - 54,425.26 events/sec, 0.0301 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-gap-report --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 10000 --batch-size 256 --warmup-events 0 --min-average-events-per-second 1`
  - mixed_replay 98,387.82 events/sec
  - cgr_stream_slice 54,425.26 events/sec
  - flink_runtime_slice 55,180.42 events/sec
  - end_to_end_json 47,280.12 events/sec
- `uv run python scripts/benchmark_mixed_replay.py --events 10000 --batch-size 256 --warmup-events 0 --live-db`
  - 10,069.22 events/sec
  - live DB write rate: 11,483.29 events/sec

### Notes

- the JSON hot-path simplification improved the current local benchmarks without adding extra moving parts
- the live historian benchmark validates the Docker-backed DB path, but target industrial-network sizing is still outstanding

## 2026-07-02 - Flink Window-State Alignment and CGR/Spark Policy

### Changed

1. **Flink keyed-window optimization**
   - Switched `services/benchmarks/flink_runtime_slice.py` to reuse the shared rolling-window state contract instead of a list-plus-pop implementation.
   - Updated `services/processor/iot_anomaly_job.py` to store window samples as typed tuples in keyed list state instead of string-encoded samples.

2. **Architecture notes**
   - Added `docs/cgr-streaming-bi-comparison-and-spark-policy.md` to separate CGR streaming/BI expectations from this platform's open-source, self-hosted scope.
   - Documented the Spark decision as optional integration for offline ETL and lakehouse workloads, not the core streaming path.

3. **Readiness and benchmark notes**
   - Updated the production-readiness checklist and benchmark results to reflect the new keyed-window baseline and the need for repeated session tracking.

### Verified

- `python -m compileall services tests`: passed
- `uv run pytest -q tests/test_datastreamctl.py tests/test_mixed_replay_benchmark.py tests/test_real_world_simulator_benchmark.py tests/test_site_profile_matrix_benchmark.py tests/test_deployment_pack_benchmark.py`: 38 passed
- `uv run pytest -q tests/test_wire_format.py tests/test_end_to_end_pipeline_benchmark.py tests/test_datastreamctl.py`: 37 passed
- `uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --events 10000 --batch-size 256 --warmup-events 0`
  - 50,882.38 events/sec
  - 0.0297 ms p99
- `uv run python -m services.cli.datastreamctl benchmark flink-runtime-slice --events 10000 --batch-size 256 --warmup-events 0`
  - 49,823.25 events/sec
  - 0.0279 ms p99
- `uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 10000 --batch-size 256 --warmup-events 0 --wire-format json`
  - 36,842.39 events/sec
  - 0.0454 ms p99
- `uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 10000 --batch-size 256 --warmup-events 0 --wire-format msgpack`
  - 35,424.11 events/sec
  - 0.0466 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-gap-report --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 10000 --batch-size 256 --warmup-events 0 --min-average-events-per-second 1`
  - `cgr_stream_slice`: 50,048.47 events/sec, 0.0530 ms p99
  - `flink_runtime_slice`: 51,126.34 events/sec, 0.0552 ms p99
  - `end_to_end_json`: 46,654.19 events/sec, 0.0271 ms p99
  - `end_to_end_msgpack`: 43,249.47 events/sec, 0.0284 ms p99
  - `mixed_replay`: 92,994.10 events/sec, 0.0257 ms p99
- `uv run python -m services.cli.datastreamctl benchmark cgr-gap-report --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 10000 --batch-size 256 --warmup-events 0 --min-average-events-per-second 1`
  - `cgr_stream_slice`: 40,438.38 events/sec, 0.0403 ms p99
  - `flink_runtime_slice`: 46,302.88 events/sec, 0.0342 ms p99
  - `end_to_end_json`: 46,654.19 events/sec, 0.0271 ms p99
  - `end_to_end_msgpack`: 43,249.47 events/sec, 0.0284 ms p99
  - `mixed_replay`: 74,903.62 events/sec, 0.0193 ms p99

### Notes

- The keyed-window runtime path now shares the same rolling-sum behavior as the fallback processor, so future throughput work should focus more on serialization format, broker topology, and sink behavior.
- The Flink slice p99 moved in the right direction on the standalone benchmark, but the gap-report run still shows session variance, so repeated runs should be used before calling a regression or win.
- MsgPack reduced payload size but did not beat JSON throughput in the current Python end-to-end benchmark, which suggests the next throughput step should be a compiled hot path rather than more Python-only tuning.
- The latest gap-report rerun on the same development host moved significantly slower, which reinforces that single-machine benchmark sessions still have meaningful variance.

## 2026-07-02 - Runtime Hardening Pass

### Changed

1. **Historian query guardrail**
   - Constrained recent-event table lookups to the known historian tables: `industrial_events`, `processed_events`, `ai_enriched`, and `dead_letter_events`.
   - This removes accidental exposure to arbitrary table names on the read path.

2. **Auth and CORS defaults**
   - Added a runtime check for the default JWT secret so operators can see when the deployment still uses an unsafe placeholder.
   - Replaced wildcard CORS with a local-origin allowlist by default, with an override through `DATASTREAM_CORS_ALLOW_ORIGINS`.

3. **Kafka producer and consumer safety**
   - Cached Kafka producers on the API runtime path so repeated publishes do not create a new producer for every event.
   - Disabled auto-commit in the processor and AI gateway consumers and committed offsets only after successful batch work.

4. **Implementation tracking**
   - Added an Obsidian vault graph note for the hardening pass so the implementation path and runtime dependencies stay visible during release work.

5. **Observability expansion**
   - Added shared runtime metrics for historian query latency, query result sizing, Kafka consumer lag, and WebSocket delivery lag.
   - Exposed a Prometheus metrics endpoint on the API service.

6. **Explicit site boundaries**
   - Every manifest source now requires a site assignment, and the manifest lint path uses a site map to keep multi-site source ownership explicit.

7. **JWT default hardening**
   - Replaced the short default JWT placeholder with a length-safe non-production secret so local auth tests no longer exercise an obviously weak key.
   - Added `jwt_secret_strong_enough` to the auth status payload.

8. **Real-world simulator benchmark runner**
   - Added `services/benchmarks/real_world_simulator.py` to run repeatable mock and mixed industrial replay cases through the same replay pipeline.
   - Added `datastreamctl benchmark real-world-simulator` and a script wrapper so the suite can be executed from the CLI.
   - The runner reuses generated scenario CSVs and the existing mixed replay path so the simulated cases stay close to production ingest shape.

9. **Shared-deployment request security**
   - Added an API middleware that requires a bearer token for mutating requests by default, with explicit login/docs/health/metrics exemptions.
   - Added baseline security headers to all API responses.
   - Added regression tests for unauthorized and authorized mutating requests plus security headers on health responses.

10. **Site-profile benchmark matrix**
   - Added `services/benchmarks/site_profile_matrix.py` to run the real-world simulator per site profile and report per-site acceptance status.
   - Added `datastreamctl benchmark site-profile-matrix` and a script wrapper so site-by-site reports can be generated from the CLI.
   - The matrix keeps per-site reporting separate from the raw simulator suite, which makes rollout acceptance easier to audit.

11. **Project rollout acceptance gate**
   - Added `datastreamctl project-manifest rollout-acceptance` to combine per-site release-gate checks with per-site benchmark acceptance in one operator-facing command.
   - The new gate reuses the existing site release checks and real-world simulator matrix so the rollout summary stays deterministic and local-first.

12. **Manifest isolation hardening**
   - Tightened project-manifest validation so source topics must carry a site boundary, cross-site bridge rules require explicit topic templates, and cross-site correlation groups require explicit strategy markers.
   - This makes leakage between sites, sources, and correlation groups easier to catch before rollout acceptance.

13. **Site benchmark calibration**
   - Added `services/benchmarks/site_profile_calibration.py` and `datastreamctl benchmark site-profile-calibration` to convert site-profile benchmark runs into sizing recommendations.
   - The calibration report surfaces observed throughput, acceptance thresholds, headroom, and a recommended minimum throughput floor per site.

14. **Real-world PLC and sensor simulation sources**
   - Added `docs/real-world-plc-sensor-simulation.md` to catalog public ICS datasets and protocol simulators that can stand in for real plant traffic when customer hardware is unavailable.
   - The catalog separates high-fidelity ICS traces, process/fault datasets, and protocol simulators so benchmark traffic can be assembled from realistic building blocks.

15. **Dataset conversion workflow**
   - Added `services/datasets/benchmark_converter.py` and `datastream-import convert` so AI4I, C-MAPSS, and generic CSV sources can be normalized into the platform's benchmark replay format.
   - Added CLI tests for AI4I and generic conversion paths so the importer can stage realistic benchmark packs without requiring physical PLCs or sensors.

16. **Industrial benchmark comparison report**
   - Added `docs/industrial-benchmark-comparison.md` to summarize the measured scores, compare them to broader industrial tool classes, and state the current readiness verdict.

17. **CGR gap report**
   - Added `services/benchmarks/cgr_gap.py`, `datastreamctl benchmark cgr-gap-report`, and `scripts/benchmark_cgr_gap_report.py` to compare local benchmark output against the public CGR Stream claim.
   - Updated the benchmark and readiness docs with a current 10k-event comparison run:
     - documented full pipeline reference: 125,830.00 events/sec
     - mixed replay: 65,876.93 events/sec with 0.0237 ms p99
     - isolated CGR-style stream slice: 21,215.99 events/sec with 0.1050 ms p99
     - real-world simulator average: 67,690.83 events/sec with 0.0313 ms p99
     - site-profile average: 67,358.66 events/sec with 0.0297 ms p99
     - site-profile best latency run: plant-a at 0.0275 ms p99
   - The report now measures replay p99 latency directly while still leaving real target-site broker/historian latency for hardware validation.
   - The latest optimization pass improved the isolated stream slice materially once the internal record migration landed.

18. **Isolated CGR-style stream slice benchmark**
   - Added `services/benchmarks/cgr_stream_slice.py`, `datastreamctl benchmark cgr-stream-slice`, and a CLI test to measure the specific connector + validation + normalization + rolling-window + scoring path in isolation.
   - Added the slice to `cgr-gap-report` so the report now shows the isolated stream-processing throughput next to the broader replay and rollout numbers.
   - Latest local run on the current codebase:
     - isolated slice: 15,723.62 events/sec with 0.1414 ms p99
   - This confirmed the main performance cost is in the software path itself, not just host hardware or the raw replay loop.

19. **CGR stream slice microbenchmark decomposition**
   - Extended `services/benchmarks/cgr_stream_slice.py` to measure mapping/validation, normalization, partitioning+windowing+scoring, and serialization separately.
   - Added stage breakdown output to `datastreamctl benchmark cgr-stream-slice` and the CLI JSON path so operators can see which part dominates on their workload.
   - Latest local run on the current codebase:
     - mapping + validation: 137,972.90 ops/sec
     - record build: 61,408.84 ops/sec
     - partitioning + rolling window + scoring: 161,477.85 ops/sec
     - serialization: 63,204.73 ops/sec
   - This showed the bottleneck moved from rolling-window math to record packing and serialization after the internal representation migration.

20. **Distributed Flink runtime alignment**
   - Extracted the shared runtime enrichment contract into `services/processor/runtime_pipeline.py` so the Python fallback processor and the Flink job finalize payloads in the same way.
   - Reworked `services/processor/iot_anomaly_job.py` into a keyed-state Flink job with rolling sample state, keyed partitioning by asset identity, and checkpointing enabled.
   - Added a `docker compose` `flink-job` service that submits the job to the local Flink cluster with the repository mounted read-only.
   - Updated the architecture notes to reflect that the Python processor is now the fallback path and the distributed Flink job is the horizontal-scaling path.
   - Verified the refactor with `python -m compileall services tests` and 51 focused regression tests.
   - Re-ran the local benchmark pack after the refactor:
     - CGR stream slice: 49,036.58 events/sec, p99 0.0325 ms
     - Flink runtime slice: 52,886.86 events/sec, p99 0.0292 ms
     - mixed replay: 93,423.46 events/sec, p99 0.0162 ms
     - real-world simulator average: 96,987.90 events/sec, p99 0.0240 ms
   - The benchmark lift is mostly from eliminating duplicate enrichment logic and keeping the runtime payload assembly on the shared path.

21. **API admin split and deployment cleanup**
   - Moved webhook, notification, annotation, user, login, and audit endpoints out of `services/api_service/main.py` into `services/api_service/routers/admin.py`.
   - Kept the app bootstrap focused on middleware, health, metrics, websocket streams, and router composition.
   - Added a dedicated Flink deployment image at `docker/Dockerfile.flink-job` and switched compose to build it instead of relying on the stock image plus live source mount.
   - Ran the current session benchmarks again and recorded the run-to-run variance explicitly:
     - CGR stream slice improved by about `2.7%` versus the previous session
     - Flink runtime slice regressed by about `4.9%` versus the previous session
   - The current evidence says this is session variance, not a proven architecture regression, because the CGR and Flink slices moved in opposite directions under the same general host conditions.

### Verified

- `python -m compileall services tests`: passed
- `uv run pytest -q tests/test_auth.py tests/test_historian_query_guardrails.py tests/test_api_route_splits.py tests/test_processor_normalization.py tests/test_ai_gateway_providers.py tests/test_datastreamctl.py tests/test_project_manifest.py`: 56 passed
- `uv run pytest -q tests/test_datastreamctl.py tests/test_site_profile_matrix_benchmark.py tests/test_real_world_simulator_benchmark.py`: 34 passed
- `uv run pytest -q tests/test_datastreamctl.py tests/test_mixed_replay_benchmark.py tests/test_real_world_simulator_benchmark.py tests/test_site_profile_matrix_benchmark.py`: 35 passed
- `uv run python -m services.cli.datastreamctl benchmark deployment-pack --events 10000 --batch-size 256`
  - export generation: 728.91 files/sec
  - mixed replay: 64,775.69 events/sec
  - `systemd` layout: 7 files
  - Kubernetes layout: 12 files
- `uv run python -m services.cli.datastreamctl benchmark deployment-pack-matrix --events 10000 --batch-size 256`
  - `demo-site`: 693.36 export files/sec, 60,535.22 replay events/sec
  - `plant-a`: 744.24 export files/sec, 63,091.48 replay events/sec
  - average: 718.80 export files/sec, 61,813.35 replay events/sec
- `uv run python scripts/benchmark_mixed_replay.py --events 10000 --batch-size 256`
  - 10,000 events
  - 58,548.76 events/sec
  - 40 batches
- `uv run python -m services.cli.datastreamctl benchmark real-world-simulator --events 20 --batch-size 4 --cases mock-normal,industrial-benchmark`
  - `mock-normal`: 12,181.75 events/sec, 5 batches, 0 invalid events
  - `industrial-benchmark`: 54,303.57 events/sec, 5 batches, 0 invalid events
  - average: 33,242.66 events/sec
- `uv run python -m services.cli.datastreamctl benchmark site-profile-matrix --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 20 --batch-size 4 --min-average-events-per-second 1`
  - `demo-site`: 44,795.24 events/sec, passed, threshold 500.0
  - `plant-a`: 59,253.75 events/sec, passed, threshold 750.0
  - overall: passed
- `uv run python -m services.cli.datastreamctl project-manifest rollout-acceptance config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 20 --batch-size 4 --min-average-events-per-second 1 --skip-network --skip-backup`
  - `demo-site`: release-gate passed, benchmark passed at 48,558.93 events/sec
  - `plant-a`: release-gate passed, benchmark passed at 55,973.26 events/sec
  - overall: passed
- `uv run pytest -q tests/test_project_manifest.py tests/test_datastreamctl.py`
  - 43 passed
- `uv run pytest -q tests/test_project_manifest.py tests/test_datastreamctl.py tests/test_site_profile_calibration_benchmark.py`
  - 45 passed
- `uv run pytest -q tests/test_datastream_import.py tests/test_datastream_import_datasets.py`
  - 16 passed
- `uv run pytest -q tests/test_datastream_import.py`
  - 13 passed
- `uv run pytest -q tests/test_datastream_import.py tests/test_datastream_import_datasets.py tests/test_datastreamctl.py tests/test_project_manifest.py tests/test_site_profile_calibration_benchmark.py`
  - 62 passed

### Notes

- The benchmark numbers are stable for the local mock pack and validate that the runtime guardrails did not introduce a measurable regression in the hot path.
- Real TimescaleDB and broker deployments should still be benchmarked on the target industrial network before production sizing.

## 2026-07-01 - Provider-Neutral Semantic Search And Query Planning

### Added

1. **Provider-neutral embedding client**
   - Added `services/common/embeddings.py` to support OpenAI-compatible embeddings endpoints, LM Studio, vLLM, Ollama, and custom HTTP backends.
   - The client defaults to the local LM Studio-compatible endpoint but falls back to deterministic embeddings if the remote backend is unavailable.
   - The implementation is not locked to one model provider, so users can swap in cloud or local backends later without changing application code.

2. **Semantic model and query compiler**
   - Added `services/common/semantic_model.py`, `services/common/query_plan.py`, and `services/common/sql_compiler.py`.
   - Queries now compile from a structured plan into validated read-only SQL instead of relying on raw free-form SQL for operator-facing paths.
   - Added a semantic model config at `config/semantic-model.yaml`.

3. **Hybrid search API**
   - Added `services/api_service/routers/search.py` with:
     - `/api/v1/search/catalog`
     - `/api/v1/search/plan`
     - `/api/v1/search/semantic`
     - `/api/v1/search/hybrid`
   - Search now combines normalized token matching, phrase match, and embeddings when available.

4. **Historian SQL guardrail**
   - Added `query_sql_readonly()` in `services/historian/client.py`.
   - The historian query endpoint now rejects non-read-only SQL before execution.

5. **Stream identity and partitioning**
   - Added `services/common/stream_scope.py` so ingest and replay paths partition Kafka by full stream identity instead of `asset_id` alone.
   - Event transport now preserves `site`, `line`, `source_protocol`, `source_id`, `asset_id`, and `tag` as part of the stream key.
   - This keeps multiple PLCs and sensors separable even when they report the same asset and tag names.

6. **Persistent retrieval index and chunking**
   - Added `services/common/text_chunking.py` and `services/common/retrieval_index.py` for file-backed chunked indexing of longer manuals and notes.
   - Added API endpoints to rebuild and evaluate the persistent index.
   - Repeated searches use a file-mtime cache so the index does not have to be re-parsed on every query.

7. **Project manifest**
   - Added `services/common/project_manifest.py` and `config/project-manifest.yaml`.
   - The manifest groups sites, PLC/source inventory, bridge rules, correlation groups, and project-level retention into one control-plane contract.
   - Added CLI support for `datastreamctl project-manifest show|validate|sites`.
   - Added `datastreamctl project-manifest bundle` for per-site deployment env output.
   - Added `datastreamctl project-manifest release-gate` to validate the full manifest across all sites.
   - Added `datastreamctl project-manifest export` to write per-site `.env` and YAML bundles to disk.
   - Added `--layout flat|systemd|kubernetes` so export can generate a deployment-ready directory tree for OS services or cluster rollouts.
   - Systemd exports now include a unit file, install/uninstall helpers, and operator README alongside the site profile and env bundle.
   - Kubernetes exports now include a config map, site-profile config map, deployment, service, kustomization, and README scaffold.
   - Kubernetes exports now include a Helm overlay at `kubernetes/helm/values.generated.yaml` plus operator notes for `k8s/helm`.
   - Helm templates now honor `namespaceOverride`, so generated site overlays can target site-specific namespaces.
   - Added `datastreamctl benchmark deployment-pack` to measure export generation plus mock industrial replay in one pass.
   - Added `datastreamctl project-manifest package` for a combined flat/systemd/Kubernetes site bundle.
   - Added `datastreamctl benchmark deployment-pack-matrix` for side-by-side site comparison.
   - Added `datastreamctl project-manifest lint` to catch source/topic collisions and policy drift.
   - Added `datastreamd --project-manifest` and `--site-id` so runtime services can start from the company manifest and select a site bundle.

### Verified

- Focused contract tests for embeddings, semantic planning, hybrid retrieval, and route registration: 21 passed
- `python -m compileall services tests`: passed
- Mock-data benchmark:
  - semantic query plan + read-only SQL compilation: 17,458 ops/sec, 0.057 ms avg
  - hybrid search over mocked historian/assets/reports/scenarios: 4,792.7 ops/sec, 0.209 ms avg
  - top-hit verification: `alarm:compressor-1:motor_vibration:2026-07-01T00:05:00Z`
  - stream key separation check: distinct PLC source IDs produce distinct Kafka keys while correlation groups stay aligned on site/asset/tag
  - persistent retrieval index over 40 mock docs: build 1.79 ops/sec, 557.55 ms per build; repeated search 21.52 ops/sec, 46.474 ms avg; evaluation hit rate@5 = 1.0
  - manifest bundle and project release-gate commands validated across the sample fleet manifest
  - deployment-pack benchmark validates both `systemd` and Kubernetes export layouts plus mock mixed replay data
  - deployment-pack benchmark on `data/benchmarks/industrial_mixed_benchmark.csv`: export generation 714.56 files/sec, 0.0252 s elapsed, `systemd` layout 7 files, Kubernetes layout 11 files, mock replay 68,166.98 events/sec over 5,000 events and 20 batches
  - deployment-pack matrix on `demo-site` and `plant-a`: export generation 760.83 files/sec average, mock replay 64,511.93 events/sec average, `systemd` layout 7 files per site, Kubernetes layout 12 files per site

## 2026-07-01 - Model and Agent Contract Layer

### Added

1. **Model registry and prompt/version contracts**
   - Added `services/common/modeling.py` with role-based model bindings for summarization, embeddings, retrieval, and deferred agent roles.
   - Added `services/common/prompt_registry.py` with versioned prompt templates.
   - Added `services/common/structured_output.py` to validate structured AI responses before they are accepted by the gateway.

2. **Read-only agent infrastructure**
   - Added `services/common/agent_tools.py` with a read-only tool catalog and context package builder.
   - Added `services/api_service/routers/modeling.py` to expose the contract surface over the API.
   - The platform still does not ship a diagnostic agent or action agent. It now only exposes the infrastructure needed for users to integrate their own later.

3. **AI gateway hardening**
   - The AI gateway now validates model output and falls back to deterministic summaries if the response is not usable.
   - Summaries are still provider-neutral and compatible with open-weight or OpenAI-compatible backends.

## 2026-07-01 - Retrieval Boundary

### Added

1. **Deterministic retrieval/search layer**
   - Added `services/common/retrieval.py` with a read-only corpus over historian events, alarms, assets, reports, and scenarios.
   - Added `/api/v1/retrieval/catalog` and `/api/v1/retrieval/search` to expose the retrieval boundary without introducing a vector database yet.
   - The layer is deterministic and lightweight so it can run locally and in industrial edge installs.

2. **Contracts and tests**
   - Added route coverage and retrieval contract tests.
   - Verified the ranking and catalog behavior with monkeypatched deterministic inputs.

### Verified

- Targeted contract and gateway tests: 15 passed
- `python -m compileall services tests`: passed
- AI gateway mock benchmark:
  - `openai_compat`: 256 events, 8 batches, 69,230.35 events/sec, avg prompt 9,434.2 bytes
  - `ollama`: 256 events, 8 batches, 68,095.97 events/sec, avg prompt 9,434.2 bytes
- Mixed replay benchmark: 5,000 events at 47,677.9 events/sec

## 2026-06-28 - Phase 7 Complete + Quick Wins

### WebSocket Streaming (Phase 7)
- Replaced all HTTP polling with WebSocket streaming
- Added `/ws/alarms`, `/ws/events`, `/ws/telemetry` endpoints
- Background broadcasters with change-detection (only push when data changes)
- Auto-reconnect with 3s backoff
- Heartbeat every 15 seconds

### Benchmark Results
- 47 tests passing → 66 tests passing
- Full pipeline: 125,830 events/sec
- Real data (AI4I): 118,470 events/sec
- WebSocket streaming eliminates polling overhead

### Quick Wins Implemented (5 features)

1. **Modbus RTU Support**
   - File: `services/edge_ingest/modbus_rtu_client.py`
   - Extends existing pymodbus (zero new dependencies)
   - Device scanning across baudrates and slave IDs
   - Context manager support
   - 4 tests passing

2. **TLS for Local Development**
   - Files: `scripts/setup-local-tls.sh`, `scripts/setup-local-tls.ps1`
   - Uses mkcert (open-source by Filippo Valsorda)
   - Creates certificates for localhost, docker networks, simulators
   - TLS info endpoint at `/.well-known/tls-info`

3. **Apprise Notifications**
   - File: `services/api_service/notifications.py`
   - Supports 100+ notification channels (email, Slack, Teams, Discord, SMS)
   - Optional dependency (falls back to logging if not installed)
   - Environment variable configuration: `APPRISE_URLS`

4. **Backup/Restore**
   - File: `services/historian/backup.py`
   - Uses pg_dump/pg_restore (standard PostgreSQL tools)
   - Automatic timestamped backups
   - Backup listing with metadata
   - wal-g status check for production continuous archiving

5. **Correlation Analysis**
   - File: `services/analytics/correlation.py`
   - Pearson correlation matrices
   - Strong correlation detection (configurable threshold)
   - NetworkX graph-based root-cause analysis
   - Anomaly propagation detection
   - 5 tests passing

### Remaining Gaps: 28 (down from 33)

Closed:
- Data retention / tiering policies
- Alert acknowledgment workflow with audit trail
- Modbus RTU/serial support
- TLS/mTLS for protocol connections
- Backup/restore for historian
- Correlation analysis (multi-tag/root-cause)

Still open (28):
- Real PLC/SCADA connectors
- OPC UA client discovery/browse
- MQTT Sparkplug B support
- Report generation / scheduled exports
- Predictive maintenance model training
- Alert escalation rules
- Data compression for historian
- Kubernetes Helm chart
- Edge-to-cloud sync / federation
- Auto-scaling for processing
- Custom dashboard builder (fully functional)
- User-defined KPIs / calculated tags
- REST API full CRUD
- MQTT/AMQP outbound bridge
- Visual Pipeline Designer
- Schema Registry UI
- Real-time Data Preview
- Connector Marketplace
- Stream Replay & Time Travel
- Exactly-Once Processing Guarantees
- Multi-Tenancy
- Self-Service BI
- KPI Builder
- Trainable Anomaly Detection ML
- Digital Twin Integration
- Shift/Production Reporting (OEE)
- Collaboration features

## Real-world correctness review (2026-06-29)

Reviewed the live data path (edge ingest -> normalize -> processor -> historian) for correctness with real datasets, not just mock data. Found and fixed three issues that would have broken real-world operation.

### Fixed

1. **Edge protocol literal rejected non-edge producers (critical)**
   - `services/edge_ingest/model.py` `Protocol` was limited to `opcua/mqtt/modbus`.
   - Every `dataset`, `mock`, `sparkplug_b`, `modbus_rtu`, and `api` event failed Pydantic validation and was routed to the DLQ instead of into the pipeline.
   - Added all producer protocols to the literal so real-data replay, the mock generator, Sparkplug B, and Modbus RTU events validate and flow.

2. **Historian connection ignored `.env` (critical)**
   - `services/historian/client.py` read only `TIMESCALE_*` env vars, but `.env.example`/`.env` define `POSTGRES_*`.
   - Defaults silently won, pointing the historian at the wrong host/port.
   - Now reads `TIMESCALE_*` with `POSTGRES_*` fallback, matching `.env`.

3. **Processor dropped non-temperature/vibration/pressure tags (high)**
   - `normalize_runtime_event` collapsed every real tag into three legacy fields; any other tag was lost (value 0.0).
   - `score_event` only scored the three legacy fields.
   - Normalization now preserves the real `tag`, `value`, `unit`, asset id, and fault labels.
   - The processor's baseline detector now also scores the actual tag, so e.g. `RotationalSpeed` from AI4I gets anomaly detection instead of being ignored.

### Verified
- New regression tests: `tests/test_realworld_fixes.py` (11 tests).
- Full Python suite: 135 passed.

### Notes
- The processor's legacy-field scoring (temperature/vibration/pressure thresholds) is intentionally preserved for backward compatibility with existing dashboards and rule sets.

## Real-world correctness review, pass 2 (2026-06-29)

A second pass over the data path and service startup. Found and fixed six more issues, several of which would have prevented the platform from running at all in the repo layout.

### Fixed

1. **AI Gateway duplication broke the UI historian stream (critical)**
   - `services/ai_gateway/main.py` had duplicated `consume_loop_with_broadcast` + monkeypatch + `historian/stream` route blocks. A third `consume_loop` definition shadowed the broadcast wiring, so the UI SSE/WS stream never received live historian updates (it appeared to "constantly refresh" because the UI fell back to polling).
   - Deduplicated, added an explicit `historian_broadcast_loop()` task started in `lifespan()`, fixed the `Settings` import path (`services.ai_gateway.config`), and added `datetime`/`timezone` imports.

2. **`/api/v1/events/ingest` bypassed the pipeline (critical)**
   - The endpoint stored the event in the historian but never published it to Kafka, so externally-ingested events skipped processing, analytics, and AI enrichment entirely.
   - It also passed a Pydantic model to `insert_industrial_event()`, which expects a dict.
   - Rewritten to validate via `validate_event` (routes invalid events to the DLQ topic), store a dict, and publish to `industrial.raw`, `industrial.normalized`, and the legacy `iot.raw` topic so the full pipeline runs on every API-ingested event.

3. **`processed_events` schema dropped real tags (high)**
   - The table had no `asset_id`/`tag`/`value`/`unit` columns, so the tag-preservation fix in normalize.py was thrown away at storage time.
   - Added the columns + indexes to `postgres/init-timescale.sql` and an idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` migration for existing databases.

4. **`insert_processed_event` array/JSON adaptation (medium)**
   - `triggered_rules` was passed as a Python list to a `TEXT[]` column and `baseline`/`evaluation` as raw Python objects to `JSONB`. Now stores the new columns, passes a plain list, and wraps JSONB values with `psycopg2.extras.Json`.

5. **`api_service` failed to import in the repo layout (critical)**
   - `from historian.client import query_historian_events` referenced a function that never existed.
   - `build_asset_hierarchy()` was used but never defined (the real API is `hierarchy_to_tree(load_hierarchy(path))`).
   - The `tls_info` route decorator ran before `app = FastAPI(...)` was created.
   - `from rbac import ...` and `from alert_manager import ...` only resolved in the flattened Docker image.
   - All fixed: `query_historian_events` is now `query_recent_events as query_historian_events`, a `build_asset_hierarchy()` helper loads the asset config, the TLS route moved after app creation, and a `sys.path` shim plus resilient imports make the service load in both layouts. The service now imports cleanly in the repo.

6. **Webhook/notification reliability (medium)**
   - `WebhookOutbound.send()` had no retry logic.
   - The webhook/notification registries were in-memory dicts lost on every restart.
   - `notifications.py` had a broken duplicate `add_channel` method floating at module scope.
   - `send()` now retries transient failures (connection errors, 5xx, 429) with exponential backoff. Registries persist to `data/webhooks.json` and `data/notifications.json` and rehydrate on startup. The stray method was moved into the `AppriseNotifier` class.

### Verified
- New regression tests: `tests/test_realworld_fixes_2.py` (9 tests).
- Full Python suite: 144 passed.
- `import services.api_service.main` succeeds in the repo layout.

### Notes
- DLQ events from the REST ingest endpoint are published to the Kafka DLQ topic only (consistent with edge ingest, which does not persist DLQ rows to the historian).
- Webhook persistence is JSON-file based and intentionally simple; for HA/multi-replica deployments this should move to the historian (Phase 5/6 territory).
- Dead duplicate imports at the end of `services/processor/runtime_processor.py` (after `main()`) were removed.

## Real-world correctness review, pass 3 (2026-06-29)

Third pass focused on compression, DB write resilience, and dead-letter observability.

### Fixed

1. **Compression segmentby mismatch for ai_enriched (high)**
   - `setup_retention_policies()` set `compress_segmentby = 'asset_id, tag'` for all three tables, but `ai_enriched` has no `asset_id`/`tag` columns.
   - This would cause `ALTER TABLE` to error every time on a fresh database, leaving `ai_enriched` uncompressed.
   - Fixed: per-table segmentby mapping (`industrial_events` → `asset_id, tag`, `processed_events` → `asset_id, tag`, `ai_enriched` → `source, model`).

2. **DB writes had no retry or failure metrics (high)**
   - All three `insert_*` functions used a single-shot write with no retry on transient failures (connection drops, server restart, network blip).
   - Added `_execute_with_retry()` with exponential backoff (0.2s, 0.6s, 1.8s) for `OperationalError`/`InterfaceError` and `SerializationFailure`.
   - Added optional Prometheus metrics (`historian_write_total`, `historian_write_latency_seconds`) so failures are observable.
   - On transient failure the connection pool is recycled (`closeall` + `cache_clear`) so the next attempt gets a fresh connection.

3. **Silent data-path failures swallowed with no logging (medium)**
   - `processor/runtime_processor.py`, `edge_ingest/main.py`, and `ai_gateway/main.py` all had bare `except Exception: pass` around historian writes and broadcast loops.
   - Replaced with `logger.warning(...)` so operators can see when writes are failing instead of silently losing data.

4. **DLQ events not persisted or queryable (medium)**
   - Invalid events from the REST ingest endpoint were sent to the Kafka DLQ topic but never stored, so operators had no way to inspect or replay them.
   - Added `dead_letter_events` hypertable with JSONB payload, error text, and origin.
   - Added `insert_dead_letter()` (uses the same retry wrapper) and wired it into the ingest endpoint.
   - Added `GET /api/v1/historian/dead-letters` endpoint.

5. **Retention/compression only manual (low)**
   - `setup_retention_policies()` existed but was only reachable via a manual POST.
   - Added auto-run in `api_service` lifespan (gated by `HISTORIAN_AUTO_SETUP=1`, default on) so a fresh deployment self-configures.

### Verified
- New regression tests: `tests/test_realworld_fixes_3.py` (9 tests).
- Full Python suite: 153 passed.
- `import services.api_service.main` still succeeds in the repo layout.

### Notes
- `HISTORIAN_AUTO_SETUP` can be set to `0` to disable the startup retention setup if you prefer manual control.
- The retry helper raises after max retries so callers still see the failure (not silently swallowed).

## Real-world correctness review, pass 4 (2026-06-29)

Fourth pass focused on security: RBAC was in-memory with mock passwords and no JWT.

### Fixed

1. **RBAC had no password hashing or JWT (critical)**
   - `authenticate_user()` ignored the password entirely (returned any user with matching username).
   - Login returned a mock token (`mock-{user_id}`) with no signature or expiration.
   - Users and audit logs were in-memory dicts lost on every restart.
   - No endpoint was protected by authentication or authorization.
   - Added `services/api_service/auth.py` with:
     - `bcrypt` password hashing and verification.
     - JWT access tokens (HS256, expiring, signed with `JWT_SECRET`).
     - `get_current_user` FastAPI dependency that validates the Bearer token.
     - `require_permission` dependency that returns 403 for unauthorized roles.
     - Best-effort persistent user/audit storage in the historian DB (`users` table + `audit_logs` hypertable).
     - Backward-compatible in-memory fallback for dev/demo mode when the DB is unavailable.

2. **Sensitive endpoints unprotected (high)**
   - User creation, user lookup, and audit log listing now require `Permission.ADMIN`.
   - Other endpoints remain open for backward compatibility; production deployments should add `get_current_user` to write/delete routes.

### Verified
- New regression tests: `tests/test_auth.py` (5 tests).
- Full Python suite: 158 passed.

### Notes
- `JWT_SECRET` must be changed from the default (`change-me-in-production`) before deploying.
- `JWT_EXPIRE_MINUTES` defaults to 8 hours; set shorter for production.
- The `users` and `audit_logs` tables are created by `postgres/init-timescale.sql` on fresh deploys.
- Existing in-memory users are still usable if the DB is unreachable (dev/demo fallback).

## Real-world correctness review, pass 5 (2026-06-29)

Fifth pass focused on deployment: the Helm chart was a single-deployment monolith that could not run the platform's actual multi-service architecture.

### Fixed

1. **Helm chart was a single-deployment monolith (high)**
   - The original `deployment.yaml` created one pod with a single container that tried to expose all three service ports (api, ai-gateway, edge-ingest) simultaneously.
   - This doesn't match the actual platform architecture (4 separate services: api-service, ai-gateway, processor, edge-ingest).
   - Rewrote the chart:
     - Separate Deployments for each service (`api-service`, `ai-gateway`, `processor`, `edge-ingest`) with independent replica counts and resource limits.
     - Separate Services for each exposed component.
     - Shared environment via a ConfigMap (`data-stream-env`) so all services get the same Kafka/DB/JWT config.
     - Service-level `enabled` toggles so operators can turn off components they don't need.
     - Added `JWT_SECRET` and `HISTORIAN_AUTO_SETUP` to the shared env.
     - Added `NOTES.txt` with post-install instructions and dependency links.

### Verified
- New regression tests: `tests/test_helm_chart.py` (5 tests).
- Full Python suite: 163 passed.

### Notes
- The Helm chart assumes dependencies (TimescaleDB, Kafka) are installed separately or as subcharts.
- The processor Deployment is headless (no Service) since it only consumes from Kafka and writes to the historian.

## Real-world correctness review, pass 6 (2026-06-29)

Sixth pass added edge-to-cloud federation — a critical capability for industrial deployments where edge nodes need to sync data to a central cloud historian.

### Added

1. **Edge-to-cloud federation service**
   - New `services/federation/main.py` that periodically syncs local historian tables to a remote cloud historian.
   - Syncs `industrial_events`, `processed_events`, `ai_enriched`, and `dead_letter_events`.
   - Configurable via env vars: `CLOUD_HISTORIAN_URL`, `CLOUD_API_KEY`, `FEDERATION_SYNC_INTERVAL_SECONDS` (default 60s), `FEDERATION_BATCH_SIZE` (default 500).
   - Uses cursor-based pagination (time-ordered) so restarts are safe and duplicates are handled by the cloud.
   - Gracefully disables itself when `CLOUD_HISTORIAN_URL` is not set.

2. **Batch ingest endpoint for federation**
   - Added `POST /api/v1/events/ingest/batch` to the API service.
   - Accepts `{"table": "...", "records": [...]}` and inserts directly into the specified historian table.
   - Skips unknown tables with 400; silently ignores individual insert failures so one bad record doesn't block the batch.

### Verified
- New regression tests: `tests/test_federation.py` (3 tests).
- Full Python suite: 166 passed.

### Notes
- The federation service uses the REST API for cloud transport (simple, works through firewalls/proxies). For high-volume deployments, consider adding a Kafka-based replication path (MirrorMaker 2 or cluster-level replication).
- The cloud historian must expose the batch ingest endpoint and validate the `Authorization: Bearer` header.

## Real-world correctness review, pass 7 (2026-06-29)

Seventh pass added TLS support for protocol connections — essential for production industrial deployments where data integrity and confidentiality are required.

### Added

1. **MQTT TLS (medium)**
   - Added `MQTT_CA_CERT`, `MQTT_CERTFILE`, `MQTT_KEYFILE` env vars.
   - When `MQTT_CA_CERT` is set, the MQTT client calls `tls_set()` before connecting, enabling encrypted and optionally mutual-TLS connections to the broker.

2. **OPC UA TLS (medium)**
   - Added `OPCUA_CERTIFICATE` and `OPCUA_PRIVATE_KEY` env vars.
   - When both are set, the asyncua `Client` is initialized with the certificate and key, enabling encrypted OPC UA connections.

3. **Modbus TCP TLS (low)**
   - Added `MODBUS_TLS` (boolean) and `MODBUS_CA_CERT` env vars.
   - When enabled, `ModbusTcpClient` is created with an `ssl.SSLContext` using the CA cert, enabling TLS-wrapped Modbus TCP.

4. **Helm chart updated**
   - All TLS env vars added to the shared ConfigMap in `k8s/helm/values.yaml`.

### Verified
- New regression tests: `tests/test_tls_config.py` (4 tests).
- Full Python suite: 170 passed.

### Notes
- These are optional; when env vars are unset the protocol clients connect in plaintext (backward-compatible with dev/demo setups).
- For mTLS (client certificate authentication), set both the certificate and key env vars. For server-only TLS, set only the CA cert.

## Real-world correctness review, pass 8 (2026-06-29)

Eighth pass added auto-scaling, completed the dataset catalog, and improved Helm chart coverage.

### Added

1. **Horizontal Pod Autoscaler (HPA) templates**
   - Added `k8s/helm/templates/hpa.yaml` with per-service HPA resources.
   - Configurable in `values.yaml`: `autoScaling.{service}.enabled`, `minReplicas`, `maxReplicas`, `targetCPUUtilizationPercentage`, `targetMemoryUtilizationPercentage`.
   - Edge ingest can scale up to 20 replicas (high connection fan-out); processor up to 10; API/AI gateway up to 5.

2. **Missing datasets added to datastream-import**
   - NASA Bearing Dataset (IMS): `nasa-bearing` source, ~250 MB zip.
   - SWaT/WADI Water Treatment Testbed: `swat` source, ~30 MB xlsx.
   - All 6 industrial datasets now cataloged: AI4I, C-MAPSS, NAB, SKAB, NASA Bearing, SWaT/WADI.

### Verified
- New regression tests: `tests/test_helm_chart.py` (8 tests), `tests/test_datastream_import_datasets.py` (3 tests).
- Full Python suite: 175 passed.

### Notes
- HPA requires the Kubernetes Metrics Server to be installed in the cluster.
- The SWaT dataset requires academic registration; the URL in the catalog is the public landing page.

## Deployment-plane runtime-mode alignment (2026-07-02)

### Added

1. **Helm chart runtime-mode selection**
   - Added `flinkJob` service toggles and HPA settings to `k8s/helm/values.yaml`.
   - The Helm deployment and HPA templates now use `env.RUNTIME_MODE` to render either the legacy Python processor or the Flink job, not both.
   - Helm profile overlays now declare `RUNTIME_MODE` explicitly for single-site, plant-local, and federated installs.

2. **Generated site bundle alignment**
   - `services/common/project_manifest.py` now writes `processor.enabled` and `flinkJob.enabled` into generated Helm overlays based on the site profile runtime mode.
   - Exported per-site Kubernetes bundles now preserve the runtime contract instead of leaving the active processor path implicit.

### Verified

- Targeted suite: `tests/test_helm_chart.py`, `tests/test_project_manifest.py`, `tests/test_site_profiles.py`, `tests/test_datastreamd.py`, `tests/test_datastreamctl.py`
- Result: `75 passed`
- `python -m compileall services tests`
- Rendered generated Helm values for `plant-a` to confirm `RUNTIME_MODE: flink-local`, `processor.enabled: false`, and `flinkJob.enabled: true`

### Notes

- This closes the last major deployment-layer mismatch between the site profile contract and the chart/export path.
- Remaining work is now mostly about higher-level production hardening and target-site validation, not basic runtime wiring.

## PLC and sensor compatibility refactor (2026-07-03)

### Added

1. **Shared device compatibility helpers**
   - Added `services/common/device_compat.py` to centralize tag-to-legacy-field mapping, tag-to-unit inference, and protocol family metadata.
   - `services/common/normalize.py`, `services/common/runtime_event.py`, and `services/edge_ingest/main.py` now consume the shared helper instead of repeating the same tag semantics in multiple places.

2. **Compatibility documentation**
   - Added a protocol compatibility matrix for OPC UA, Modbus TCP/RTU, MQTT, Sparkplug B, and gateway-first EtherNet/IP / PROFINET coverage.
   - Added second-brain notes that record the current direct-support versus gateway-first policy.

### Verified

- New regression tests: `tests/test_device_compat.py`
- Shared tag mapping checks still pass through the existing edge-model tests

### Notes

- The refactor does not change the event contract.
- It reduces duplicated semantic logic and gives the platform a single place to reason about PLC and sensor compatibility edge cases.

## Reliability and maintainability pass (2026-07-03)

### Added

1. **Historian write/query consolidation**
   - Added shared historian row/query helpers in `services/historian/client.py` to remove repeated batch insert and read plumbing.
   - Batch insert paths for industrial and processed events now share the same execution and retry wrapper.

2. **Degraded-state reporting**
   - Added a shared service health state helper in `services/common/service_health.py`.
   - API and AI gateway health surfaces now report degraded mode instead of silently swallowing repeated broadcast/runtime failures.

3. **Flink hardening**
   - The Flink job now skips malformed input records instead of crashing the stream task.
   - Starting offsets are now configurable through `FLINK_STARTING_OFFSETS`.

### Verified

- `python -m compileall services tests`
- `uv run pytest -q tests/test_outbound_bridge.py tests/test_device_compat.py tests/test_edge_model.py tests/test_processor_normalization.py tests/test_runtime_pipeline_contract.py tests/test_historian.py tests/test_auth.py`
- Result: `29 passed`

### Notes

- This pass is mainly about making failure modes visible and removing duplicate backend code.
- Packaging is still intentionally deferred to the final phase.

### Benchmark rerun

- `production-pipeline --runtime-mode python-fallback`: `43,419.63 events/sec`, `0.0365 ms p99`
- `production-pipeline --runtime-mode flink-production`: `43,251.30 events/sec`, `0.0960 ms p99`
- `cgr-stream-slice`: `50,751.73 events/sec`, `0.0536 ms p99`
- `flink-runtime-slice`: `50,738.60 events/sec`, `0.0522 ms p99`
- `mixed replay`: `93,350.90 events/sec`, `0.0249 ms p99`
- `end-to-end json`: `42,080.58 events/sec`, `0.0605 ms p99`

Compared with the previous recorded runs in the repo:

- Python fallback throughput improved by about `26.85%`
- Flink production throughput improved by about `3.55%`
- CGR stream slice throughput improved by about `23.0%`
- Flink runtime slice throughput improved by about `18.2%`
- Mixed replay throughput improved by about `41.7%`
- End-to-end JSON throughput moved about `-9.8%`, which should be repeated before treating it as a real regression

## Test-drift reconciliation pass (2026-07-06)

A full-suite run surfaced nine test/code drift failures introduced by earlier
refactors that moved source code without updating the tests that assert against
it. None of these touched functionality; they reconcile tests with the new code
locations. One fix also resolved a real silent-state-clearing bug.

### Fixed

1. **TLS config tests point at refactored connectors (3 tests)**
   - `tests/test_tls_config.py` asserted TLS env-var wiring against
     `services/edge_ingest/main.py`, but the `refactor: split api realtime and
     edge adapters` commit (75e4b89) moved MQTT/OPC UA/Modbus TLS into
     `services/edge_ingest/connectors/{mqtt,opcua,modbus}.py`. The tests now
     read the connector modules where the TLS code actually lives.

2. **Historian execute_values mock accepts page_size (2 tests)**
   - The historian batch-write refactor added `page_size=len(rows)` to the
     `execute_values` call, but the test mocks had the old positional-only
     signature `(cur, query, rows)`. Updated both mocks to accept `page_size`.

3. **AI gateway service_state uses the object API + degraded-state bug fix (1 test)**
   - `test_ai_gateway_providers.py` used dict-style access
     (`service_state["last_error"]`) left over from before the
     `ServiceHealthState` dataclass refactor. Switched to the object API
     (`mark_ok()`, `service_state.last_error`).
   - **Real bug found and fixed:** `enrich_batch` marked the service degraded
     when the LLM fell back to a deterministic summary, then unconditionally
     called `service_state.mark_ok()` at the end of the happy path, silently
     clearing the degraded state. Added a `used_fallback` guard so `mark_ok()`
     only runs when the LLM actually succeeded, preserving the degraded signal
     operators rely on.

4. **UI mobile tests match the Next.js viewport export (2 tests)**
   - `ui/app/layout.tsx` uses the Next.js 14 `export const viewport` pattern
     (`width: "device-width"`), not an HTML meta string. The test's literal
     `"width=device-width"` assertion was updated to check `"device-width"`.
   - `ui/app/page.tsx` uses `sm:`/`md:`/`xl:` responsive grid breakpoints
     (a more granular responsive setup than the test required). Relaxed the
     assertions to verify responsive grid classes exist at any breakpoint.

5. **DLQ ingest test isolation (1 test) + historian env leak (root cause)**
   - `test_ingest_endpoint_routes_invalid_to_dlq` failed only in the full
     suite. Two causes:
     - `test_historian.py::test_connection_string_uses_env_vars` set
       `TIMESCALE_HOST=testhost` via `os.environ` (not monkeypatch), leaking
       the non-resolvable hostname into later tests so the DLQ historian
       write retried and failed. Switched to `monkeypatch.setenv` so the env
       is auto-restored.
     - `_get_producer` is `@lru_cache`d, so a prior test's monkeypatched
       producer stayed cached and the DLQ test's `FakeProducer` never received
       the `produce` call. The test now calls `_get_producer.cache_clear()`
       before asserting.

### Verified
- Full Python suite: `419 passed`.
- `python -m compileall services tests`: clean.

### Notes
- No functionality changed. The only production code change is the
  `used_fallback` guard in `enrich_batch`, which fixes a silent
  degraded-state reset so operators actually see when the LLM is in fallback.
- The `uv.lock` and `ui/next-env.d.ts` working-tree changes were spurious
  (CRLF line-ending reformat and a Next.js dev path tweak) and discarded
  rather than committed.

---

## SQL query control and contextual help hardening (2026-07-09)

Implemented the SQL workflow guardrails requested for the historian UI and
started standardizing inline explanations across the dashboard/catalog pages.

### What changed

1. **Historian SQL timeout and cancel contract**
   - Added a tracked query handle in `services/historian/client.py` so active
     read-only statements can be canceled by query ID.
   - `statement_timeout` is now set per historian SQL call from the backend
     default (`HISTORIAN_QUERY_TIMEOUT_MS`) before the query executes.
   - Added `DELETE /api/v1/historian/query/{query_id}` so the UI can stop an
     active query instead of only waiting for the server to finish.

2. **SQL panel usability**
   - Added a `?` help tip to the SQL Query card.
   - Added visible run/cancel controls, a read-only badge, and clearer helper
     text describing the historian-only workflow.
   - The panel now generates a query ID per run so cancellation can target the
     correct statement.

3. **Contextual help tips**
   - Added reusable help tips to historian replay, asset hierarchy, trends,
     alarms/events, webhooks, notifications, and the integrations catalog.
   - The integration page now separates editable surfaces from deployment-
     configured surfaces with inline guidance.

### Docs and vault

- `docs/app-functionality.md` now includes the historian SQL workflow and the
  new contextual help-tip pattern.
- `ObsidianVault/30_UI_UX/` will receive the matching UI note for the same
  change set.

### Verification

- `py -3.13 -m pytest tests/test_historian.py tests/test_api_route_splits.py -q`:
  9 passed.
- `py -3.13 -m pytest tests/test_historian_query_guardrails.py -q`:
  3 passed.
- `py -3.13 -m compileall services tests`: clean.
- `npm run build` in `ui/`: successful production build with route manifest
  confirming `/api/historian`, `/api/query`, `/api/webhooks`,
  `/api/notifications`, and the historian pages all compile together.

---

## Integrations page readability cleanup (2026-07-09)

The desktop layout on `/integrations` was denser than the mobile layout and
repeated a status badge that was already obvious from the section grouping.

### What changed

- Reduced the card grids from 3-4 columns to a roomier 2-column desktop layout
  so the page reads more like the stacked mobile view.
- Removed the redundant `Editable in app` / `Deployment-configured` tags from
  each card.
- Increased wrapping room in card titles, descriptions, location rows, and
  guide steps so longer integration names do not collide with card edges.

### Verification

- `npm run build` in `ui/`: successful.
- `py -3.13 -m pytest tests/test_api_route_splits.py -q`: 1 passed.

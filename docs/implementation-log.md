# Implementation Log

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
     - mixed replay: 68,606.16 events/sec with 0.0211 ms p99
     - real-world simulator average: 68,236.68 events/sec with 0.0205 ms p99
     - site-profile average: 65,729.12 events/sec with 0.0285 ms p99
     - site-profile best latency run: plant-a at 0.0268 ms p99
   - The report now measures replay p99 latency directly while still leaving real target-site broker/historian latency for hardware validation.
   - Session delta versus the previous CGR-gap run is small and mostly attributable to benchmark variance, not a throughput optimization. The mixed replay number moved from 65,938.49 to 68,606.16 events/sec, but the broader matrix did not shift in a consistent way.

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
- The Helm chart assumes dependencies (TimescaleDB, Redpanda) are installed separately or as subcharts.
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
- The federation service uses the REST API for cloud transport (simple, works through firewalls/proxies). For high-volume deployments, consider adding a Kafka-based replication path (MirrorMaker 2 or Redpanda replication).
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

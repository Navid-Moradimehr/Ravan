# Implementation Log

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

### Verified

- Targeted contract and gateway tests: 13 passed
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

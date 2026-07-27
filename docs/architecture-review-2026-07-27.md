# Architecture and Production-Readiness Review

Date: 2026-07-27

## Executive verdict

Ravan has a credible industrial-data-platform shape and substantially more
engineering depth than a demo repository: canonical events, protocol adapters,
Kafka boundaries, a Flink runtime, at-least-once projections, Timescale
hypertables, replay/dataset tooling, deployment assets, metrics, and broad
tests are all present.

It is suitable for a controlled single-site deployment and a serious pilot,
with production readiness depending on deployment-specific commissioning. The
main blockers are correctness and operational boundaries:

- the Kubernetes topology did not deploy all workers required by the Compose
  data flow, while edge horizontal scaling could duplicate source reads;
- the AI Gateway mixed asynchronous HTTP with synchronous Kafka/database work;
- processing-mode selection could render a chart with no active processor;
- several control-plane registries are intentionally process-local or
  JSON-file-backed for local-first operation and require an external ownership
  decision before API horizontal scaling;
- Python and Flink remain distinct runtime profiles and require conformance
  testing when switching between them.

Authentication and authorization are intentionally deployment-owned extension
points. The platform supplies integration hooks and local defaults; operators
must provide their identity, policy, tenant, and site-scope enforcement.

This platform must remain outside safety-instrumented and direct actuator
control loops. Its architecture is appropriate for telemetry, analytics,
historian, reporting, and advisory workflows.

## Repository shape

- Python: roughly 48,000 lines across services, tools, and tests.
- TypeScript/TSX: roughly 8,600 lines in the Next.js operator UI and BFF.
- Test surface: 157 Python test modules.
- Runtime technologies: FastAPI, Kafka, Flink/PyFlink, Timescale/Postgres,
  Redis, MinIO/Iceberg, Prometheus/Grafana, Next.js, Tauri, and optional Rust
  acceleration.

## Current architecture and complete data flow

### Write path

1. Source definitions are written by the API into the connection registry.
2. `services.edge_ingest.main` periodically reloads enabled definitions and
   starts OPC UA, MQTT/Sparkplug B, Modbus TCP/RTU, REST, or discovery adapters.
3. Each adapter sends a protocol mapping to `EdgePublisher`.
4. `EdgePublisher` emits:
   - the source payload to `industrial.raw`;
   - a validated canonical event to `industrial.normalized`;
   - a compatibility projection to `iot.raw`;
   - invalid/clock-rejected/oversized input to `industrial.dlq`.
5. HTTP push follows a parallel ingress path through the API runtime and emits
   the same raw, normalized, and compatibility topics.
6. `normalized_fanout` consumes `industrial.normalized` and writes configured
   historian, lakehouse, or downstream-Kafka sinks.
7. Exactly one processing mode should consume `industrial.normalized`:
   - `runtime_processor` keeps local rolling windows; or
   - `iot_anomaly_job` keeps Flink keyed state and checkpoints.
8. Processing emits deterministic enrichment to `iot.processed`.
9. `processed_fanout` projects `iot.processed` into TimescaleDB.
10. The AI gateway consumes `iot.processed`, records durable report jobs,
    invokes a configured model or deterministic fallback, and emits
    `iot.ai_enriched`.
11. `ai_enriched_fanout` projects AI events to the historian/configured sinks.
12. Optional operational, observation-artifact, and raw-archive consumers
    project their topics into Iceberg/MinIO or other configured sinks.
13. Federation uses MirrorMaker for selected normalized/operational topics;
    the platform does not own plant control.

### Read path

1. TimescaleDB is the operational query model for recent events, trends,
   alarms, processed events, AI reports, metadata, and lineage.
2. FastAPI domain routers expose those projections plus control-plane
   registries.
3. API WebSocket tasks poll historian projections and broadcast changes to
   connections held by the current process.
4. The Next.js application calls same-origin route handlers.
5. Those handlers proxy to the API service or AI gateway.
6. Grafana reads Prometheus; the UI also proxies selected observability data.

### Control and deployment path

- `datastreamctl` validates profiles, manifests, releases, backups, and
  benchmark gates.
- `datastreamd` supervises the host-run Python surface.
- Compose is the most complete runnable topology.
- Helm currently deploys API, AI gateway, one processor mode, edge ingest, and
  optional Flink resources, expecting Kafka/Timescale externally. It does not
  express all projection workers present in Compose.

## What is good

- Kafka is used as the primary decoupling boundary rather than writing directly
  from edge connectors into every downstream store.
- Canonical event construction and stream partition keys are centralized.
- Python and Flink processing share the main enrichment contract.
- Projection workers commit Kafka offsets after strict sink success.
- Historian writes are batched and use idempotent conflict handling.
- Flink has checkpoint/savepoint configuration and keyed state.
- Threshold-policy propagation uses a database outbox and Kafka topic.
- The project has unusually broad contract, resilience, benchmark, deployment,
  and UI build coverage for a beta codebase.
- Secrets are represented by references in source definitions instead of being
  deliberately exposed in the UI.

## Critical problem areas

### P0: production blockers

1. **Kubernetes topology was incomplete and unsafe to scale blindly.** The Helm
   chart omits normalized, processed, and AI projection workers that the
   documented data flow depends on. Its edge HPA can create multiple replicas
   that independently connect to the same physical sources, producing duplicate
   telemetry. Edge ownership needs leader election, explicit sharding, or a
   fixed replica count per source assignment.

2. **State ownership is intentionally local-first.** Webhooks, notifications, connection and
   sink registries, delivery history, collaboration data, replay status, and
   some model/assistant metadata are stored in memory or JSON files. This works
   for one process on one writable volume, not for multiple API replicas.

3. **Migration ownership is fragmented.** Schema creation appears in bootstrap
   SQL, the `timescaledb-migrate` shell command, and application startup helpers.
   Use one versioned migration system with immutable revisions, upgrade/rollback
   procedures, and a deployment gate.

4. **No production HA defaults.** Compose uses one Kafka broker with replication
   factor one, one Timescale instance, local Flink checkpoint storage, and
   development credentials. This is acceptable for evaluation only.

### P1: correctness and scalability risks

1. **Two processing runtimes are two operational products.** Shared enrichment
   reduces algorithm drift, but startup offsets differ, state persistence
   differs, threshold transition state differs, poison-record behavior differs,
   and the Python runtime cannot scale statefully like Flink. Declare Python as
   development-only or build an explicit conformance suite and migration path.

2. **Flink poison records can cause a restart loop.** Invalid normalized input
   raises from the process function instead of being side-output to a DLQ with
   a controlled offset policy.

3. **Realtime delivery is process-local and polling-based.** Every API replica
   owns a separate WebSocket set. Polling Timescale and comparing full result
   arrays is wasteful and does not provide consistent multi-replica delivery.
   Use Kafka/Redis/NATS pub-sub for change notifications, bounded per-client
   queues, and explicit slow-consumer handling.

4. **Synchronous work blocked async services.** The AI Gateway now runs Kafka
   consumer operations on a single dedicated executor and offloads historian and
   report-job calls. API realtime queries are also moved off the event loop.

5. **Flink rolling-window updates are O(window size).** The process function
   materializes `ListState` into a Python list for every event and rewrites it
   after eviction. At higher cardinality/rates, use a ring buffer or aggregate
   state with indexed eviction and configure state TTL.

6. **Unbounded/local caches require lifecycle rules.** Python rolling windows
   had pruning controls, but threshold transition state did not share their
   lifecycle. Flink keyed state also needs an explicit TTL appropriate to
   device cardinality and offline periods.

7. **Connection pool sizing is static per process.** A maximum of ten historian
   connections becomes `10 * replicas * workers`, while background polling
   consumes the same pool. Set deployment-wide budgets, expose pool metrics,
   and use a pooler such as PgBouncer where appropriate.

### P2: maintainability and “pizza/spaghetti” code

1. `services/cli/datastreamctl.py` is a large module of roughly 2,700 lines.
   This is acceptable for the local-first CLI; split it only when ownership or
   test isolation requires it.
2. `services/historian/client.py` is a large procedural repository covering
   events, queries, semantic models, audits, retention, compression, and schema
   setup.
3. `services/api_service/main.py` contains import-path mutation, flattened-image
   compatibility imports, middleware, lifecycle work, health probes, and router
   assembly. `_prune_legacy_routes` is compatibility scaffolding rather than a
   clean composition root.
4. `services/ai_gateway/main.py` combines HTTP routes, SSE, Kafka consumption,
   durable job execution, historian broadcasts, prompting, validation, and
   output publishing.
5. Fan-out consumers repeat nearly identical poll/decode/DLQ/batch/commit/
   shutdown loops.
6. Historian single-row and batch insert functions duplicate field mapping and
   SQL column definitions.
7. Next.js BFF route handlers repeatedly implement base-URL selection, header
   forwarding, fetch, JSON parsing, and error conversion. Defaults are
   inconsistent between `localhost` and Compose-only DNS names.
8. Configuration is spread across environment reads in many modules, Compose,
   Helm values, site profiles, and scripts without one validated typed runtime
   configuration.
9. Broad `except Exception` handling is common. Some cases are legitimate
   availability boundaries, but several silently convert misconfiguration into
   empty data or degraded behavior, making diagnosis difficult.

## Duplicate logic inventory

- Python and Flink window/threshold runtime adapters.
- Normalized, processed, AI, operational, artifact, and raw-archive Kafka
  consumer shells.
- Historian scalar conversion and row construction in single/batch functions.
- Next.js API proxy handlers.

## 2026-07-27 hardening completed in this working tree

- Edge partial batches now have an idle timer flush.
- Processor and fan-out delivery paths commit offsets only after successful
  publication or sink acknowledgement.
- Threshold state follows window eviction and historian pooled connections are
  rolled back before reuse.
- Append-only industrial event topics use retention rather than compaction.
- AI Gateway Kafka operations are single-threaded off the ASGI loop; historian
  and durable report operations are offloaded to worker threads.
- Helm defaults now select the Python fallback explicitly, validate that exactly
  one processing runtime is active, deploy the core normalized/processed/AI
  fan-outs, and reject edge horizontal scaling.

The remaining items above are deployment and product-policy work, not reasons
to reject the architecture outright. Kubernetes HA, external identity,
multi-replica state ownership, migration governance, and Flink state tuning
must be validated for each industrial installation.
- Dataset/training bundle writers with repeated manifest, lineage, channels,
  quality report, and `_SUCCESS` logic.
- Project-manifest renderers for package, flat, Windows, systemd, Kubernetes,
  and Helm output.
- Topic setup previously existed in Compose and two PowerShell scripts with
  different policies.
- Environment defaults are restated across Python settings, Compose, Helm, UI
  route handlers, and documentation.

## Clean target architecture

### 1. Edge adapter plane

- Protocol plugins implement `SourceAdapter -> AsyncIterator[SourceRecord]`.
- A canonical ingress application service owns validation, mapping, clock
  policy, idempotency key, and publishing.
- A durable local outbox/spool has an explicit byte quota, replay order,
  corruption handling, and metrics.
- A source-assignment lease ensures one active reader per physical source.

### 2. Event backbone

- Separate append-only event topics from compacted metadata topics.
- Contracts live in a real schema registry with compatibility enforcement.
- Topic specs are declarative and generated into Compose/Kubernetes/operator
  tooling from one source.
- Production partition count, replication factor, retention, min ISR, and ACLs
  are deployment policy, not hard-coded demo values.

### 3. Stream-processing plane

- Flink is the production processor; the Python runtime is a local conformance
  runner.
- Pure domain functions perform normalization/scoring/threshold evaluation.
- Runtime adapters own state, watermarks, checkpointing, DLQ side outputs, and
  delivery guarantees.
- All state has documented TTL and rescaling semantics.

### 4. Projection plane

- Reusable `KafkaBatchProjector` owns poll, bounded buffering, decode, DLQ,
  retry classification, commit, lag, and shutdown.
- Small projection handlers map one event family to Timescale, Iceberg, search,
  or external integrations.
- Database writes are idempotent by a globally stable event identity.
- Outbox/inbox tables handle cross-system commands and callbacks.

### 5. Control plane

- FastAPI is a composition root over domain application services.
- Domain packages expose ports (`ConnectionRepository`, `PolicyRepository`,
  `ReportJobRepository`) and do not import HTTP/Kafka/SQL implementations.
- All mutable shared state uses Postgres/Redis or another explicitly selected
  clustered store.
- Authentication and authorization are enforced centrally for HTTP, SSE,
  WebSocket, metrics, and documentation endpoints.

### 6. Query/realtime plane

- Query repositories are separate from schema management and write
  repositories.
- Read models are indexed and bounded.
- Kafka/Redis change notifications feed a shared realtime gateway.
- Each client has a bounded queue, backpressure policy, resume cursor, and
  authorization scope.

### 7. AI/reporting plane

- API creates durable jobs only.
- Worker deployments claim jobs, load bounded evidence, call provider adapters,
  validate structured output, and publish an immutable result event.
- Model calls never share an event loop with Kafka polling or UI streaming.
- Deterministic fallback and model output remain distinguishable in contracts
  and SLOs.

### 8. Delivery and operations

- One migration tool and one declarative topic specification.
- Compose is explicitly a development/evaluation target.
- Helm includes every required worker and prohibits unsafe autoscaling modes.
- Production profiles require external secrets, TLS/mTLS, network policies,
  Pod security contexts, anti-affinity, disruption budgets, backups, restore
  tests, and observable SLOs.

## Refactoring strategy

### Phase 0: production gate

1. Fail closed on auth and secrets in production profiles.
2. Add read/WebSocket authorization and site/role scopes.
3. Make the Helm topology data-flow complete; disable edge HPA until source
   leasing exists.
4. Adopt versioned migrations and remove DDL from runtime startup.
5. Define production Kafka/Timescale/Flink HA requirements.
6. Add a real end-to-end test with Kafka, Timescale, process restart, duplicate
   delivery, and checkpoint recovery.

### Phase 1: stabilize boundaries

1. Extract `KafkaBatchProjector` and migrate one fan-out at a time.
2. Extract historian event, processed-event, semantic, audit, and maintenance
   repositories.
3. Split the CLI into command modules with a small parser/composition root.
4. Replace BFF copy/paste with one typed proxy helper and centralized service
   URL configuration.
5. Create one typed `RuntimeSettings` tree and generate deployment environment
   contracts from it.

### Phase 2: make state scalable

1. Move file-backed mutable registries to Postgres repositories.
2. Add source leases/assignments for edge HA.
3. Replace historian polling with shared pub-sub realtime events.
4. Add state TTL to Flink and cardinality/size metrics to all caches.
5. Run Kafka consumption outside ASGI event loops.

### Phase 3: prove operation

1. Add ruff/formatting, mypy or pyright, ESLint, and dependency/security scans
   to CI.
2. Test both clean install and upgrade migrations.
3. Establish soak targets for throughput, p99 latency, loss, duplicates,
   backlog recovery, database saturation, and source reconnect storms.
4. Chaos-test broker loss, Timescale failover, Flink restart/rescale, full
   edge-spool recovery, and AI provider timeout.
5. Publish a supported deployment matrix and capacity envelope.

## Production-grade improvements made during this review

- Edge partial batches are now serviced on a timer, so a quiet source cannot
  leave normalized events buffered forever.
- The Python processor now waits for Kafka delivery before historian work and
  source-offset commit, flushes low-rate batches while idle, preserves failed
  batches, and closes resources even when final flush fails.
- Python threshold transition state now uses the same full partition key as
  rolling-window state and is removed when that stream is pruned.
- Historian connections now roll back read or failed transactions before
  returning to the pool, preventing idle-in-transaction sessions.
- API health uptime now measures process lifetime rather than request duration.
- API realtime queries run off the event loop and background polling stops when
  no relevant clients are connected.
- AI report-memory lookup is nonblocking and degrades gracefully when the
  historian is unavailable.
- Append-only Kafka event topics now use delete/retention policy; only threshold
  metadata is compacted. Existing topics are altered as well as new topics
  created.
- Duplicate PowerShell topic ownership was reduced to one implementation.
- Missing benchmark CLI imports/parser registrations were restored.
- The built-in mock dataset was restored to the runtime catalog and explicit
  empty catalogs are respected.
- Regression tests cover timed edge flush, Kafka-before-offset ordering, failed
  delivery preservation, and topic retention policy.

## Validation evidence

- Targeted changed-path tests: passed.
- Next.js production build and TypeScript check: passed.
- Docker Compose profile configuration: passed.
- Helm lint: passed.
- Python compileall: passed.
- Initial broad suite: 715 passed, 22 failed, 1 skipped. Ten failures were due
  to `pyarrow`/`tahutils` missing from the local virtualenv (and the lakehouse
  module failed collection for the same missing `pyarrow` dependency in the
  first attempt); the remaining code regressions were addressed.
- Final dependency-independent broad suite: 720 passed, 1 skipped. Changed-path
  tests, including threshold-state lifecycle checks, were also run separately
  after the final edits.

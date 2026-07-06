# Data Streaming & Writing Pipeline — Audit Findings and Remediation Plan (2026-07-06)

This document records the current findings from a full trace of every producer
→ topic → consumer → sink → historian write path, explains why each finding
matters, and lays out the concrete remediation plan. It is the companion to
`docs/session-changes-and-rationale.md` (which covers already-shipped changes).

The audit was non-mutating: it traced code, configs, SQL schemas, and compose
wiring. No code was changed to produce these findings.

---

## Verified topology

```
Edge adapters (MQTT/OPC UA/Modbus)
  └─ EdgePublisher (idempotent producer, acks=all, composite partition key)
       ├─ industrial.raw        (raw payload, before validation)
       ├─ industrial.normalized (validated IndustrialEvent, keyed)
       ├─ iot.raw               (legacy shape via to_legacy_iot_event, keyed)
       └─ industrial.dlq        (invalid / oversize)

industrial.normalized
  ├─ [normalized-fanout group]  → CompositeSink(SINKS env) → historian / lakehouse / kafka
  └─ [runtime-iot-processor]    (reads iot.raw via IOT_TOPIC — see note)

iot.raw (IOT_TOPIC)
  └─ [runtime-iot-processor]    → iot.processed topic  +  historian.processed_events (DUAL WRITE)

iot.processed
  └─ [outbound-bridge group]    → MQTT / AMQP downstream (enable.auto.commit=True)

iot.ai_enriched
  └─ [ai-enriched-fanout group] → historian.ai_enriched
```

### What is already correct (no action needed)

- **Message keys / partitioning:** a composite key
  `project|site|line|protocol|source_id|asset_id|tag` is produced by
  `services/common/stream_scope.py::stream_partition_key` (with a Rust
  fastpath). This guarantees per-asset ordering within a partition — the
  earlier concern about "does Kafka use a message key" is satisfied.
- **Producer durability:** `EdgePublisher` uses `enable.idempotence=True`,
  `acks=all`, `retries=10`, bounded internal buffer with backpressure on
  `BufferError`, and routes oversize messages to the DLQ instead of dropping
  them.
- **Consumer groups are distinct:** `normalized-fanout`, `runtime-iot-processor`,
  `ai-gateway`, `outbound-bridge`, `ai-enriched-fanout`. No accidental shared
  group stealing partitions.
- **At-least-once on the hot paths:** `normalized_fanout` and
  `ai_enriched_fanout` commit offsets manually *after* the sink/insert succeeds
  (`enable.auto.commit=False`).
- **Dedup on industrial + dead-letter tables:** `insert_industrial_event(s)`
  and `insert_dead_letter` use `ON CONFLICT (event_id) DO NOTHING`, backed by
  unique indexes in `docker/postgres/init-timescale-full.sql`.
- **Sink abstraction:** the `Sink` protocol + `CompositeSink` + `SinkRegistry`
  decouples "what is produced" from "where it lands," so users can plug in
  endpoint datasets via the `SINKS` env var. This directly answers the earlier
  question about whether sinks make the platform compatible with varied
  endpoints — yes, and the pattern is already in place for the normalized path.

---

## Findings (priority order)

### Finding 1 — `processed_events` writes have no dedup (DATA INTEGRITY)

**Where:** `services/historian/client.py` — `insert_processed_event` (line ~251)
and `insert_processed_events` (line ~296).

**What:** Both `processed_events` INSERT statements omit
`ON CONFLICT (event_id) DO NOTHING`. The industrial-events and dead-letter
inserts have it; the processed-events inserts do not. The table *does* have a
unique index (`processed_events_event_id_uniq` in `init-timescale-full.sql`),
so the missing clause is inconsistent with the schema.

**Impact:** The pipeline is at-least-once (offset committed after write). On a
consumer restart or Kafka redelivery, the same `event_id` is re-inserted. With
the unique index present, Postgres raises a unique-violation instead of
deduplicating — the batch write fails, the offset is never committed, and the
processor/fan-out stalls on that partition. Without the index, it would
silently duplicate rows. Either way it is broken.

**Plan:** add `ON CONFLICT (event_id) DO NOTHING` to both `processed_events`
INSERT statements, matching the industrial-events pattern exactly. Add a test
asserting the clause is present.

---

### Finding 2 — Python runtime processor dual-writes to historian unconditionally (DUPLICATE LOGIC / DATA RISK)

**Where:** `services/processor/runtime_processor.py` line ~82.

**What:** The Python runtime processor consumes `iot.raw`, produces to the
`iot.processed` topic, **and** writes directly to `historian.processed_events`
in the same loop, then commits the offset only after the historian write. This
is the same dual-write anti-pattern already removed from the API ingest path
(commit `5e93262` — "remove api ingest dual-write"). The Flink job already
gates its equivalent write behind `FLINK_PERSIST_PROCESSED_EVENTS=1`.

**Impact:**
- Couples the processor to the historian; a historian outage stalls processing.
- If an operator ever routes `iot.processed` through a sink fan-out (the
  intended decoupled pattern), processed events are written twice.
- Inconsistent with the Flink path, which gates the same behavior.

**Plan:** gate the historian write behind `RUNTIME_PERSIST_PROCESSED_EVENTS`
(default `"1"` to preserve current behavior). When disabled, the processor
only produces `iot.processed` and commits offsets after the produce — matching
the normalized fan-out decoupling. Document the tradeoff. This keeps
functionality identical by default while letting operators choose full
decoupling.

---

### Finding 3 — Kafka topics are not created at compose startup (COLD-START FAILURE)

**Where:** `docker/kafka/server.properties` (`auto.create.topics.enable=false`)
and `docker/docker-compose.yml` (no topic-init step).

**What:** Auto-creation is intentionally off (good practice), but nothing in
compose creates the six required topics (`industrial.raw`,
`industrial.normalized`, `industrial.dlq`, `iot.raw`, `iot.processed`,
`iot.ai_enriched`). Topic creation today depends on manually running
`scripts/create-industrial-topics.ps1` — PowerShell-only, Windows-only, and
not wired into compose. On a fresh `docker compose up` on Linux/macOS,
producers/consumers hit `UnknownTopicOrPartitionError` until manual
intervention.

**Impact:** broken cold start on any non-Windows host; the platform appears
dead until a manual step is remembered.

**Plan:** add a one-shot `kafka-init` service to `docker/docker-compose.yml`
(`depends_on: kafka healthy`) that runs
`kafka-topics.sh --create --if-not-exists` for all six topics (3 partitions,
replication-factor 1). Keeps `auto.create` off. Cross-platform. Update the
self-host install guide to note topics are now auto-created.

---

### Finding 4 — Divergent topic scripts and SQL schemas (CONFIG CORRUPTION RISK)

**Where:**
- `scripts/create-industrial-topics.ps1` — 6 topics at 3 partitions.
- `scripts/create-topics.ps1` — a different overlapping set; `iot.ai_enriched`
  at **1 partition** (disagrees with the other script's 3); plus Kafka Connect
  internal topics.
- `docker/postgres/init.sql` — mounted by the plain `postgres` service
  (compose line 48). A **legacy demo schema**: `event_id UUID PRIMARY KEY`,
  `ts_source` column, no hypertables, no `processed_events` /
  `dead_letter_events` / unique indexes. Completely incompatible with the
  historian client (which inserts `event_id TEXT`, column `time`, etc.).
- `postgres/init-timescale.sql` — lacks the `_event_id_uniq` indexes that
  `docker/postgres/init-timescale-full.sql` (the one the `timescaledb` service
  actually uses) has.

**Impact:** if anyone uses the plain `postgres` service instead of
`timescaledb`, every historian write fails. The two PS1 scripts disagree on
partition counts, so "which topics exist" depends on which script was run.

**Plan:**
- Delete `docker/postgres/init.sql` and `postgres/init-timescale.sql`
  (dead/divergent). Single schema source of truth =
  `docker/postgres/init-timescale-full.sql`.
- Replace the two PS1 scripts with the compose `kafka-init` step (Finding 3),
  or keep exactly one as a standalone fallback and delete the other.

---

### Finding 5 — Outbound bridge uses `enable.auto.commit=True` (AT-LEAST-ONCE WEAKENED)

**Where:** `services/edge_ingest/outbound_bridge.py` line ~53.

**What:** The outbound bridge consumes `iot.processed` with
`enable.auto.commit=True`. Its `_forward_mqtt` / `_forward_amqp` methods
swallow exceptions (`except Exception: return`). So if a forward to the
downstream MQTT/AMQP endpoint fails, the offset is still auto-committed and
the record is never retried — silent data loss to downstream sinks.

**Impact:** the at-least-once guarantee that the rest of the pipeline
carefully maintains is broken at the last hop for MQTT/AMQP egress.

**Plan:** set `enable.auto.commit=False` and commit manually *after* a
successful forward, matching the `normalized_fanout` pattern. On forward
failure, log + increment a metric and skip the commit so the record is
retried on the next poll. (Routing forward failures to a DLQ is optional and
out of scope unless requested.)

---

## Lower-priority observations (document only, no fix now)

- **`ai_enriched` table has no `event_id` / dedup.** Acceptable: each row is an
  append-only summary batch, not an idempotent event. Leaving as-is.
- **Single-broker Kafka** (`replication.factor=1`, no `min.insync.replicas`).
  Fine for the OSS dev/single-node default. The idempotent producer + `acks=all`
  is correct for the configured topology. Production needs ≥3 brokers and
  `min.insync.replicas=2` — to be documented in the deployment guide, not
  changed in the default config.
- **`_get_producer` `@lru_cache`** in `api_service/runtime.py`. Fine at runtime;
  only caused a test-isolation issue, already fixed last session.

---

## Remediation plan (decision-complete)

### Historian dedup (Finding 1)
- `services/historian/client.py`: add `ON CONFLICT (event_id) DO NOTHING` to
  `insert_processed_event` and `insert_processed_events`.
- Test: `test_insert_processed_events_uses_on_conflict` asserting the clause.

### Processor dual-write gate (Finding 2)
- `services/processor/runtime_processor.py`: wrap the historian write in
  `if persist_processed:` where
  `persist_processed = os.getenv("RUNTIME_PERSIST_PROCESSED_EVENTS", "1") == "1"`.
- When disabled, commit offsets after producing to `iot.processed`.
- Default `1` preserves current behavior.

### Compose topic init (Finding 3)
- `docker/docker-compose.yml`: add `kafka-init` one-shot service creating the
  six topics idempotently.

### Dead-code/schema removal (Finding 4)
- Delete `docker/postgres/init.sql`, `postgres/init-timescale.sql`.
- Consolidate the two PS1 topic scripts into the compose init (keep one as
  fallback if desired).

### Outbound bridge at-least-once (Finding 5)
- `services/edge_ingest/outbound_bridge.py`: `enable.auto.commit=False`,
  manual commit after successful forward; skip commit on failure.

### Tests
- `test_insert_processed_events_uses_on_conflict` (Finding 1).
- `test_runtime_processor_persist_gate` — with the flag off, assert no
  historian call and offset still committed (Finding 2).
- Extend compose test to assert `kafka-init` and the six topics (Finding 3).
- `test_outbound_bridge_commits_only_on_success` (Finding 5).
- Full suite must stay green (baseline 419).

### Docs & vault
- Append "Data pipeline integrity audit (2026-07-06)" to
  `docs/implementation-log.md` and `docs/production-readiness-checklist.md`.
- Update `ObsidianVault/20_Architecture/System Architecture.md` and
  `Sink Architecture.md` with the corrected topology.
- Update `docs/self-host-install-guide.md`: topics auto-created by compose.

## Assumptions / defaults chosen

- `RUNTIME_PERSIST_PROCESSED_EVENTS` defaults to `1` (current behavior). Full
  decoupling (processor never dual-writes) is opt-in.
- `auto.create.topics.enable` stays `false`; the compose init replaces it.
- Single schema truth = `docker/postgres/init-timescale-full.sql`.
- Outbound-bridge failures retry (at-least-once); no DLQ unless requested.
- No security/authn/authz changes (standing constraint).


---

## Remediation status — implemented (2026-07-06)

All five findings are implemented, tested, and committed individually. The
full test suite stayed green throughout (final: 429 passed, 0 failed).

| Finding | Commit | Result |
|---|---|---|
| 1 — processed_events dedup | `bee8953` | `ON CONFLICT (event_id) DO NOTHING` added to single + batch inserts; +1 test |
| 2 — processor dual-write gate | `b6eca10` | `RUNTIME_PERSIST_PROCESSED_EVENTS` (default `1`); `_flush_processed_batch` extracted to module level; +4 tests |
| 3 — compose topic init | `8ea9d29` | `kafka-init` one-shot service creates all 6 topics idempotently; +5 tests |
| 4 — divergent schema/script cleanup | `ffc4e07` | **Expanded:** fixed broken init-SQL mounts (see below); removed stale `postgres/init-timescale.sql`; reconciled topic scripts |
| 5 — outbound bridge at-least-once | `5c8dc71` | `enable.auto.commit=False`; forwarders return bool; commit only on success; +5 tests |

### Finding 4 — higher-impact bug found during remediation

The audit flagged divergent SQL schemas, but tracing the compose bind mounts
revealed a more serious defect: both database services referenced paths under
`./postgres/` that **do not exist on disk**. The real schema files live in
`docker/postgres/`. Docker Compose silently binds an empty directory for a
missing source path, so a fresh `docker compose up` ran the `timescaledb` and
`postgres` services with **no init schema** — no hypertables, no unique dedup
indexes, and no `orders` table for the Debezium CDC demo.

Fixes applied:
- `timescaledb` service mount corrected to `./docker/postgres/init-timescale-full.sql`.
- `postgres` service mount corrected to `./docker/postgres/init.sql`.
- `postgres/init-timescale.sql` deleted (stale; lacked unique indexes). The two
  schema tests that referenced it now point at the canonical schema.
- `docker/postgres/init.sql` **retained** — it is the Debezium `orders` CDC demo
  schema (a separate database/purpose), not a duplicate of the historian schema.
- `scripts/create-topics.ps1` reconciled with the canonical topic set: added
  `industrial.raw`/`industrial.normalized`/`industrial.dlq`, fixed
  `iot.ai_enriched` to 3 partitions to match `kafka-init`. Connect-internal
  compact topics kept (legitimately Connect-specific).

### Canonical schema / topic source of truth

- Historian schema: `docker/postgres/init-timescale-full.sql` (unique indexes
  `_event_id_uniq` on industrial/processed/dead-letter events; hypertables).
- Debezium CDC demo schema: `docker/postgres/init.sql`.
- Topic provisioning: `docker/docker-compose.yml` `kafka-init` service is the
  canonical, platform-agnostic source; `scripts/create-industrial-topics.ps1`
  and `scripts/create-topics.ps1` are manual fallbacks now aligned with it.

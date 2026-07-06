# Competitive Comparison Evaluation (2026-07-06)

Source: `comparission.md` — a managed Kafka/streaming platform (10 pillars).
Scope: identify features/tests/structure inspirations compatible with our
open-source, Kafka-based industrial-streaming architecture. Redpanda is out of
scope by design (we intentionally use Kafka in KRaft mode).

## Pillar-by-pillar comparison

| # | Their pillar | Our current state | Gap | Worth borrowing? |
|---|--------------|-------------------|-----|------------------|
| 01 | Managed Kafka cluster (KRaft, rolling upgrade, rack-aware, Strimzi/Ansible) | Kafka KRaft, single node, `auto.create=false`, RF=1, no rack-aware, no rolling-upgrade automation | Operations tooling | **Low** — they sell managed ops; we're an app. Document desired prod settings instead. |
| 02 | Flink + ksqlDB stateful (RocksDB, incremental ckpt, event-time watermarks, exactly-once) | Flink job exists, `AT_LEAST_ONCE`, no RocksDB/incremental ckpt config, no ksqlDB, no explicit event-time | Stream-processing depth | **Medium-High** — config-only upgrades (checkpoint mode, RocksDB backend, incremental ckpt) are cheap and high-value. ksqlDB = optional add. |
| 03 | Kafka Connect + 80 connectors + SMT | Debezium Connect image configured; no SMT/masking; sinks are our own Python `Sink` layer | Connector breadth | **Low-Medium** — our sink layer is the right OS pattern; document Connect for DB CDC. |
| 04 | Debezium CDC (Oracle/PG/MySQL, incremental snapshot, schema change tracking) | Debezium image present; no configured connectors; we write via API/fanout | CDC integration | **Medium** — document a Debezium PG connector recipe (incremental snapshot). Compatible. |
| 05 | MQTT 5.0 broker (QoS 0/1/2, retained, LWT, 2M conns, bridge→Kafka per-device key) | paho client + mosquitto; QoS 1 only in sim; no retained/LWT; bridge is our edge publisher | MQTT maturity | **High** — retained messages + Last Will + QoS config + per-device partition key are directly applicable. |
| 06 | Exactly-once end-to-end (idempotent prod, transactional sink, Flink 2PC, chaos tests) | idempotent producers + acks=all + event_id dedup (at-least-once). No transactions, no 2PC, no chaos tests | Delivery semantics + tests | **High** — chaos/replay tests for failover; make ON CONFLICT dedup explicit as the EOS strategy. |
| 07 | Lag/health monitoring (Burrow, Cruise Control, Prometheus, alerts) | Per-partition lag gauge → Prometheus + Grafana; no Burrow/Cruise; alerts via webhook | Observability completeness | **Medium** — add lag alert thresholds; Cruise Control is overkill for OS. |
| 08 | Tiered storage + long retention (S3 cold, replay from offset, AES-256) | No Kafka tiered storage; long-term data goes to our Iceberg lakehouse (Phase 5) | Cold storage strategy | **Low** — our lakehouse IS the tiered/cold store. Document replay-from-lakehouse. |
| 09 | MirrorMaker 2 multi-region (active-active, offset translation, DR drill) | None; single region | DR/geo-replication | **Low for OS** — enterprise concern; document as ops extension point. |
| 10 | Schema Registry + safe evolution (Avro/Proto/JSON, backward/forward compat) | In-memory SchemaRegistry (JSON, no compatibility enforcement, no Avro/Proto serialization) | Schema governance depth | **High** — add compatibility-mode enforcement on register; this is a real gap. |

## Recommended inspirations (compatible with OS + our structure)

### High value, low effort
1. **Schema Registry compatibility enforcement** (pillar 10) — add a
   `compatibility` field per schema and a `register()` guard that rejects
   backward-incompatible field removals. Pure Python, fits our in-memory registry
   and open-source "validate in app code" stance (ADR 0002).
2. **MQTT maturity** (pillar 05) — add configurable QoS, retained-message, and
   Last-Will support to the MQTT connector; keep per-device/per-asset partition
   key (we already use the 7-field composite key). Fits `services/edge_ingest`.
3. **Chaos/replay delivery tests** (pillar 06) — add tests that simulate
   consumer crash mid-batch and assert the fan-out's at-least-once + event_id
   dedup produces no duplicates. Fits our existing test patterns.

### High value, medium effort
4. **Flink checkpoint depth** (pillar 02) — configure exactly-once checkpoint
   mode, RocksDB state backend, and incremental checkpoints via env vars. Config
   only; no new code paths.
5. **CDC recipe** (pillar 04) — document a Debezium PostgreSQL connector
   configuration (incremental snapshot, `pgoutput`) as an ingestion alternative
   to the API/edge path. The Connect image already ships.
6. **Lag alerting** (pillar 07) — add Prometheus alert rules on the existing
   `datastream_broker_consumer_lag_messages` gauge (threshold + anomaly).

### Skip (enterprise-managed-ops, not OS-core)
- Managed cluster ops / Strimzi / Ansible rolling upgrades (pillar 01)
- Cruise Control (pillar 07)
- Kafka tiered storage (pillar 08) — our Iceberg lakehouse covers cold storage
- MirrorMaker 2 / multi-region DR (pillar 09)

## Verdict
Their platform is an enterprise *managed Kafka* product; ours is an
*open-source industrial streaming application*. They overlap on Kafka/Flink/
MQTT/Schema but their differentiation (managed ops, multi-region, 80 connectors)
is not our target. The genuinely useful, structure-compatible inspirations are
the **app-layer** ones: schema compatibility enforcement, MQTT QoS/retained/LWT,
delivery-chaos tests, Flink checkpoint config, and a Debezium CDC recipe.

## Implementation Status (2026-07-06)

All three high-value, low-effort inspirations are now implemented and committed:

| # | Inspiration | Status | Tests | Commit |
|---|-------------|--------|-------|--------|
| 1 | Schema registry compatibility enforcement | Done | `tests/test_schema_registry_compat.py` (13) | `273bcdf` |
| 2 | MQTT QoS / retained / Last-Will | Done | `tests/test_mqtt_qos_will.py` (5) | `a70d742` |
| 3 | Delivery chaos / replay dedup | Done | `tests/test_delivery_chaos.py` (3) | `07fe7ab` |

The medium-effort inspirations (Flink checkpoint config, Debezium CDC recipe, lag
alerting) remain documented as future work; they are config/docs-only and do not
require code changes. See [[20_Architecture/Schema Governance]],
[[20_Architecture/Industrial Edge Pipeline]], [[20_Architecture/Sink Architecture]].

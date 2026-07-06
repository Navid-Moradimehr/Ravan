# Debezium PostgreSQL CDC Ingest

> Competitive inspiration 6 (pillar 04 - Debezium CDC). Added 2026-07-06.

## When to use this

The default ingest path is the API service + edge adapters (MQTT/OPC UA/Modbus)
producing `industrial.raw`. Debezium Change Data Capture is an **alternative
ingestion path** for data that already lives in a relational database: it
streams row-level inserts/updates/deletes from the Postgres WAL into Kafka
without application polling.

Typical use cases:
- Backfilling / mirroring an existing `orders` or asset-registry table.
- Capturing writes from a third-party system that writes directly to Postgres.
- Incremental snapshot of a large existing table without locking.

This is **optional** and does not replace the industrial event stream; it adds a
CDC source alongside it. Open-source adopters enable it only when they have a
database to capture.

## Prerequisites (already satisfied in the compose dev stack)

- `postgres` service runs with `wal_level=logical` (set in `docker-compose.yml`).
- The `orders` table has `REPLICA IDENTITY FULL` (in `docker/postgres/init.sql`).
- A logical publication `dbz_orders` is created for `public.orders`
  (`docker/postgres/init.sql`). The connector can also auto-create it via
  `publication.autocreate.mode=filtered`.
- The `connect` service (`debezium/connect:3.0.0.Final`) is wired to Kafka with
  JSON converters (schemas disabled to match the platform's envelope style).

## Register the connector

```bash
# From the repo root, after `docker compose up` has started connect.
docker/debezium/register-connectors.sh
# Or target a different Connect REST endpoint:
docker/debezium/register-connectors.sh http://connect-host:8083
```

The script deletes any existing connector with the same name, then POSTs the
config in `docker/debezium/pg-orders-source.json` and lists the registered
connectors. Re-running is idempotent and keeps the repo config authoritative.

## What it produces

- Topic: `pg.public.orders` (one row = one event).
- The `ExtractNewRecordState` SMT (Single Message Transform) unwraps the
  Debezium envelope so consumers receive the new row state directly, drops
  tombstones, and rewrites deletes as a row with `__deleted=true`.
- Incremental snapshots are enabled, so the initial backfill is chunked
  (`incremental.snapshot.chunk.size=1024`) without a table lock.
- Key/value converters are JSON with schemas disabled, matching the platform's
  lightweight envelope convention.

## Connector config

`docker/debezium/pg-orders-source.json` - the source of truth. Key fields:

| Field | Value | Why |
|-------|-------|-----|
| `plugin.name` | `pgoutput` | PostgreSQL native logical decoding plugin (PG10+) |
| `slot.name` | `debezium_orders` | Logical replication slot |
| `publication.name` | `dbz_orders` | Matches the publication in init.sql |
| `publication.autocreate.mode` | `filtered` | Auto-create publication for captured tables |
| `snapshot.mode` | `initial` | Backfill existing rows on first start |
| `incremental.snapshot.mode` | `incremental` | Lock-free backfill in chunks |
| `transforms` | `unwrap` | ExtractNewRecordState: consumers get the new row |

## Downstream integration

CDC events land on `pg.public.orders`. They are **not** industrial events, so
they do not flow through the `industrial.normalized` fan-out. Consumers that
need them subscribe directly to the CDC topic. To route a CDC table into the
normalized stream, add a processor that maps the CDC row to the
`industrial_event` schema and publishes to `industrial.raw` (or write a custom
sink). This mapping is intentionally **not** automated, since CDC sources are
user-specific.

## Related

- [[20_Architecture/Industrial Edge Pipeline]]
- `comparission.md` pillar 04

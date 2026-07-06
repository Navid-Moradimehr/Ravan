CREATE TABLE IF NOT EXISTS orders (
    id SERIAL PRIMARY KEY,
    customer_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'created',
    amount NUMERIC(12, 2) NOT NULL,
    currency TEXT NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE orders REPLICA IDENTITY FULL;

INSERT INTO orders (customer_id, status, amount, currency)
VALUES
    ('customer-001', 'created', 129.95, 'USD'),
    ('customer-002', 'paid', 82.10, 'USD')
ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS industrial_events (
    event_id UUID PRIMARY KEY,
    source_protocol TEXT NOT NULL,
    source_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    value_text TEXT NOT NULL,
    quality TEXT NOT NULL,
    unit TEXT,
    site TEXT NOT NULL,
    line TEXT NOT NULL,
    ts_source TIMESTAMPTZ NOT NULL,
    ts_ingest TIMESTAMPTZ NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS industrial_events_asset_ts_idx ON industrial_events (asset_id, ts_source DESC);
CREATE INDEX IF NOT EXISTS industrial_events_protocol_ts_idx ON industrial_events (source_protocol, ts_source DESC);

-- Logical replication publication for Debezium CDC on the orders table.
-- pgoutput + wal_level=logical (set on the postgres service) are required.
-- The Debezium connector reads this publication via a logical slot.
-- The connector can also auto-create this (publication.autocreate.mode=filtered),
-- but defining it here keeps the prerequisite explicit and works without
-- connector-side DDL privileges in restricted deployments.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_publication WHERE pubname = 'dbz_orders'
    ) THEN
        CREATE PUBLICATION dbz_orders FOR TABLE public.orders;
    END IF;
END $$;

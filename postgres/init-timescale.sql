-- TimescaleDB schema for Local Stream Engine historian

CREATE EXTENSION IF NOT EXISTS timescaledb;

-- Raw normalized events
CREATE TABLE IF NOT EXISTS industrial_events (
    time TIMESTAMPTZ NOT NULL,
    event_id TEXT,
    source_protocol TEXT,
    source_id TEXT,
    asset_id TEXT,
    tag TEXT,
    value DOUBLE PRECISION,
    quality TEXT,
    unit TEXT,
    site TEXT,
    line TEXT,
    schema_version INT,
    fault_type TEXT,
    scenario_id TEXT,
    ground_truth_severity TEXT,
    step INT
);

SELECT create_hypertable('industrial_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_industrial_events_asset ON industrial_events (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_industrial_events_tag ON industrial_events (tag, time DESC);
CREATE INDEX IF NOT EXISTS idx_industrial_events_scenario ON industrial_events (scenario_id, time DESC);

-- Processed events with analytics
CREATE TABLE IF NOT EXISTS processed_events (
    time TIMESTAMPTZ NOT NULL,
    event_id TEXT,
    device_id TEXT,
    asset_id TEXT,
    tag TEXT,
    value DOUBLE PRECISION,
    unit TEXT,
    site_id TEXT,
    source_protocol TEXT,
    quality TEXT,
    schema_version INT,
    temperature_c DOUBLE PRECISION,
    vibration_mm_s DOUBLE PRECISION,
    pressure_bar DOUBLE PRECISION,
    processed_at TIMESTAMPTZ,
    window_size INT,
    temperature_avg_c DOUBLE PRECISION,
    vibration_avg_mm_s DOUBLE PRECISION,
    anomaly_score DOUBLE PRECISION,
    severity TEXT,
    triggered_rules TEXT[],
    baseline JSONB,
    evaluation JSONB
);

SELECT create_hypertable('processed_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_processed_events_device ON processed_events (device_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_processed_events_severity ON processed_events (severity, time DESC);
CREATE INDEX IF NOT EXISTS idx_processed_events_asset ON processed_events (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_processed_events_tag ON processed_events (tag, time DESC);

-- Dead-letter events: records that failed validation and were not ingested.
-- Persisted so operators can inspect/replay rejected data, not just dropped.
CREATE TABLE IF NOT EXISTS dead_letter_events (
    time TIMESTAMPTZ NOT NULL,
    event_id TEXT,
    source_protocol TEXT,
    source_id TEXT,
    error TEXT,
    payload JSONB,
    schema_version INT,
    origin TEXT
);

SELECT create_hypertable('dead_letter_events', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_dead_letter_source ON dead_letter_events (source_protocol, time DESC);
CREATE INDEX IF NOT EXISTS idx_dead_letter_event_id ON dead_letter_events (event_id);

-- AI enriched events
CREATE TABLE IF NOT EXISTS ai_enriched (
    time TIMESTAMPTZ NOT NULL,
    source TEXT,
    model TEXT,
    batch_size INT,
    summary TEXT,
    latency_seconds DOUBLE PRECISION
);

SELECT create_hypertable('ai_enriched', 'time', if_not_exists => TRUE);

-- Idempotent migration: add tag/asset/value/unit columns to processed_events
-- for databases created before these columns existed. Safe to re-run.
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS asset_id TEXT;
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS tag TEXT;
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS value DOUBLE PRECISION;
ALTER TABLE processed_events ADD COLUMN IF NOT EXISTS unit TEXT;
CREATE INDEX IF NOT EXISTS idx_processed_events_asset ON processed_events (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_processed_events_tag ON processed_events (tag, time DESC);

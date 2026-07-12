CREATE EXTENSION IF NOT EXISTS timescaledb;

CREATE TABLE IF NOT EXISTS metadata_asset_tags (
    site_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    unit TEXT,
    source TEXT NOT NULL DEFAULT 'observed',
    first_seen TIMESTAMPTZ,
    last_seen TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (site_id, asset_id, tag)
);

CREATE INDEX IF NOT EXISTS metadata_asset_tags_lookup_idx ON metadata_asset_tags (site_id, asset_id, tag);
CREATE INDEX IF NOT EXISTS metadata_asset_tags_updated_idx ON metadata_asset_tags (updated_at DESC);

CREATE TABLE IF NOT EXISTS industrial_events (
    time TIMESTAMPTZ NOT NULL,
    event_id UUID NOT NULL,
    source_protocol TEXT NOT NULL,
    source_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    quality TEXT NOT NULL DEFAULT 'good',
    unit TEXT,
    site TEXT NOT NULL DEFAULT 'demo-site',
    line TEXT NOT NULL DEFAULT 'line-01',
    schema_version INTEGER NOT NULL DEFAULT 1,
    fault_type TEXT NOT NULL DEFAULT 'normal',
    scenario_id TEXT NOT NULL DEFAULT 'sc-000',
    ground_truth_severity TEXT NOT NULL DEFAULT 'normal',
    step INTEGER NOT NULL DEFAULT 0,
    value_text TEXT GENERATED ALWAYS AS (value::text) STORED
);

SELECT create_hypertable('industrial_events', 'time', if_not_exists => TRUE, migrate_data => TRUE);

CREATE INDEX IF NOT EXISTS industrial_events_asset_ts_idx ON industrial_events (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS industrial_events_protocol_ts_idx ON industrial_events (source_protocol, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS industrial_events_event_id_uniq ON industrial_events (time, event_id);

CREATE TABLE IF NOT EXISTS processed_events (
    time TIMESTAMPTZ NOT NULL,
    event_id UUID NOT NULL,
    device_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    unit TEXT,
    site_id TEXT,
    source_protocol TEXT NOT NULL,
    quality TEXT NOT NULL DEFAULT 'good',
    schema_version INTEGER NOT NULL DEFAULT 1,
    temperature_c DOUBLE PRECISION NOT NULL DEFAULT 0,
    vibration_mm_s DOUBLE PRECISION NOT NULL DEFAULT 0,
    pressure_bar DOUBLE PRECISION NOT NULL DEFAULT 0,
    processed_at TIMESTAMPTZ,
    window_size INTEGER NOT NULL DEFAULT 0,
    temperature_avg_c DOUBLE PRECISION NOT NULL DEFAULT 0,
    vibration_avg_mm_s DOUBLE PRECISION NOT NULL DEFAULT 0,
    anomaly_score DOUBLE PRECISION NOT NULL DEFAULT 0,
    severity TEXT NOT NULL DEFAULT 'normal',
    triggered_rules TEXT[] NOT NULL DEFAULT '{}',
    baseline JSONB,
    evaluation JSONB
);

SELECT create_hypertable('processed_events', 'time', if_not_exists => TRUE, migrate_data => TRUE);
CREATE INDEX IF NOT EXISTS processed_events_asset_ts_idx ON processed_events (asset_id, time DESC);
CREATE INDEX IF NOT EXISTS processed_events_severity_ts_idx ON processed_events (severity, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS processed_events_event_id_uniq ON processed_events (time, event_id);

CREATE TABLE IF NOT EXISTS ai_enriched (
    time TIMESTAMPTZ NOT NULL,
    source TEXT NOT NULL,
    model TEXT NOT NULL,
    batch_size INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    latency_seconds DOUBLE PRECISION NOT NULL DEFAULT 0
);

SELECT create_hypertable('ai_enriched', 'time', if_not_exists => TRUE, migrate_data => TRUE);
CREATE INDEX IF NOT EXISTS ai_enriched_source_ts_idx ON ai_enriched (source, time DESC);

CREATE TABLE IF NOT EXISTS dead_letter_events (
    time TIMESTAMPTZ NOT NULL,
    event_id UUID NOT NULL,
    source_protocol TEXT NOT NULL,
    source_id TEXT NOT NULL,
    error TEXT NOT NULL,
    payload JSONB NOT NULL,
    schema_version INTEGER NOT NULL DEFAULT 1,
    origin TEXT NOT NULL DEFAULT 'unknown'
);

SELECT create_hypertable('dead_letter_events', 'time', if_not_exists => TRUE, migrate_data => TRUE);
CREATE INDEX IF NOT EXISTS dead_letter_events_origin_ts_idx ON dead_letter_events (origin, time DESC);
CREATE UNIQUE INDEX IF NOT EXISTS dead_letter_events_event_id_uniq ON dead_letter_events (time, event_id);

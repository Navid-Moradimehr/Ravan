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

-- Semantic plane: ontology packs, graph entities and lineage records.
CREATE TABLE IF NOT EXISTS semantic_ontology_packs (
    pack_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    layer TEXT NOT NULL,
    version TEXT NOT NULL,
    concepts TEXT[] NOT NULL DEFAULT '{}',
    notes TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_entities (
    entity_id TEXT PRIMARY KEY,
    entity_type TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    labels TEXT[] NOT NULL DEFAULT '{}',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_relationships (
    relationship_id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    relationship_type TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_measurements (
    measurement_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    name TEXT NOT NULL,
    unit TEXT NOT NULL DEFAULT '',
    minimum DOUBLE PRECISION,
    maximum DOUBLE PRECISION,
    warning_low DOUBLE PRECISION,
    warning_high DOUBLE PRECISION,
    critical_low DOUBLE PRECISION,
    critical_high DOUBLE PRECISION,
    sampling_rate_hz DOUBLE PRECISION,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_observations (
    observation_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    value JSONB,
    source_id TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_actions (
    action_id TEXT PRIMARY KEY,
    actor_id TEXT NOT NULL,
    target_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    document_type TEXT NOT NULL DEFAULT 'document',
    uri TEXT NOT NULL DEFAULT '',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_locations (
    location_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location_type TEXT NOT NULL,
    parent_id TEXT,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_states (
    state_id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    state TEXT NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_workflows (
    workflow_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workflow_type TEXT NOT NULL DEFAULT 'workflow',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_events (
    event_id TEXT PRIMARY KEY,
    event_type TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS semantic_lineage (
    lineage_id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    source_id TEXT NOT NULL,
    target_id TEXT NOT NULL DEFAULT '',
    entity_id TEXT NOT NULL DEFAULT '',
    relationship_id TEXT NOT NULL DEFAULT '',
    site_id TEXT NOT NULL DEFAULT '',
    dataset_id TEXT NOT NULL DEFAULT '',
    model_version TEXT NOT NULL DEFAULT '',
    processing_version TEXT NOT NULL DEFAULT '',
    occurred_at TIMESTAMPTZ NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_semantic_entities_type ON semantic_entities (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_semantic_relationships_type ON semantic_relationships (relationship_type, relationship_id);
CREATE INDEX IF NOT EXISTS idx_semantic_observations_entity ON semantic_observations (entity_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_semantic_lineage_site ON semantic_lineage (site_id, occurred_at DESC);

SELECT create_hypertable('semantic_observations', 'observed_at', if_not_exists => TRUE);
SELECT create_hypertable('semantic_actions', 'occurred_at', if_not_exists => TRUE);
SELECT create_hypertable('semantic_events', 'occurred_at', if_not_exists => TRUE);
SELECT create_hypertable('semantic_lineage', 'occurred_at', if_not_exists => TRUE);

ALTER TABLE semantic_observations ADD COLUMN IF NOT EXISTS source_id TEXT NOT NULL DEFAULT '';
ALTER TABLE semantic_events ADD COLUMN IF NOT EXISTS source_id TEXT NOT NULL DEFAULT '';

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

-- Users and audit logs for RBAC + security
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    role TEXT NOT NULL,
    email TEXT,
    password_hash TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    time TIMESTAMPTZ NOT NULL,
    user_id TEXT,
    action TEXT,
    resource TEXT,
    details JSONB
);

SELECT create_hypertable('audit_logs', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs (user_id, time DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs (action, time DESC);

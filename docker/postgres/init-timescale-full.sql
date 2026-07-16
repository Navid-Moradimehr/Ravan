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

CREATE TABLE IF NOT EXISTS audit_logs (
    time TIMESTAMPTZ NOT NULL DEFAULT now(),
    user_id TEXT NOT NULL DEFAULT '',
    action TEXT NOT NULL,
    resource TEXT NOT NULL DEFAULT '',
    details JSONB NOT NULL DEFAULT '{}'::jsonb
);
CREATE INDEX IF NOT EXISTS audit_logs_time_idx ON audit_logs (time DESC);
CREATE INDEX IF NOT EXISTS audit_logs_resource_idx ON audit_logs (resource, time DESC);

CREATE TABLE IF NOT EXISTS metadata_threshold_policies (
    site_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    unit TEXT,
    mode TEXT NOT NULL DEFAULT 'outside_range',
    warning_low DOUBLE PRECISION,
    warning_high DOUBLE PRECISION,
    critical_low DOUBLE PRECISION,
    critical_high DOUBLE PRECISION,
    deadband DOUBLE PRECISION NOT NULL DEFAULT 0,
    on_delay_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    off_delay_seconds DOUBLE PRECISION NOT NULL DEFAULT 0,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    source TEXT NOT NULL DEFAULT 'user',
    version INTEGER NOT NULL DEFAULT 1,
    effective_from TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (site_id, asset_id, tag)
);
CREATE INDEX IF NOT EXISTS metadata_threshold_policies_site_idx ON metadata_threshold_policies (site_id, asset_id, tag);

CREATE TABLE IF NOT EXISTS metadata_threshold_policy_outbox (
    outbox_id BIGSERIAL PRIMARY KEY,
    policy_key TEXT NOT NULL,
    site_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    policy_version INTEGER NOT NULL,
    payload JSONB NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS metadata_threshold_policy_outbox_status_idx ON metadata_threshold_policy_outbox (sync_status, outbox_id);
CREATE INDEX IF NOT EXISTS metadata_threshold_policy_outbox_policy_idx ON metadata_threshold_policy_outbox (policy_key, policy_version);

CREATE TABLE IF NOT EXISTS industrial_events (
    time TIMESTAMPTZ NOT NULL,
    event_id UUID NOT NULL,
    source_protocol TEXT NOT NULL,
    source_id TEXT NOT NULL,
    asset_id TEXT NOT NULL,
    tag TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL DEFAULT 0,
    value_text TEXT,
    value_text_raw TEXT,
    value_bool BOOLEAN,
    value_type TEXT NOT NULL DEFAULT 'number',
    quality TEXT NOT NULL DEFAULT 'good',
    unit TEXT,
    site TEXT NOT NULL DEFAULT 'demo-site',
    line TEXT NOT NULL DEFAULT 'line-01',
    schema_version INTEGER NOT NULL DEFAULT 1,
    fault_type TEXT NOT NULL DEFAULT 'normal',
    scenario_id TEXT NOT NULL DEFAULT 'sc-000',
    ground_truth_severity TEXT NOT NULL DEFAULT 'normal',
    step INTEGER NOT NULL DEFAULT 0
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
    threshold_severity TEXT NOT NULL DEFAULT 'normal',
    threshold_status TEXT NOT NULL DEFAULT 'unconfigured',
    threshold_source TEXT NOT NULL DEFAULT 'unconfigured',
    threshold_policy_version INTEGER NOT NULL DEFAULT 0,
    threshold_breached BOOLEAN NOT NULL DEFAULT FALSE,
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

CREATE TABLE IF NOT EXISTS metadata_ai_reporting_policy (
    policy_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL UNIQUE,
    policy JSONB NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS ai_report_jobs (
    job_id UUID PRIMARY KEY,
    site_id TEXT NOT NULL,
    report_type TEXT NOT NULL,
    trigger_reason TEXT NOT NULL,
    window_start TIMESTAMPTZ,
    window_end TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'pending',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    policy_snapshot JSONB NOT NULL,
    evidence JSONB NOT NULL DEFAULT '[]'::jsonb,
    result JSONB,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ai_report_jobs_status_idx ON ai_report_jobs (status, next_attempt_at);
CREATE UNIQUE INDEX IF NOT EXISTS ai_report_jobs_window_uniq ON ai_report_jobs (site_id, report_type, trigger_reason, window_start, window_end);

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

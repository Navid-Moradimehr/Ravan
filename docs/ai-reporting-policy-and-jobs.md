# AI Reporting Policy and Jobs

Status: Phase 2 implementation design

## Boundary

AI reporting is a governed consumer of processed industrial events. It is not part
of the deterministic historian or the stream scoring path. The reporting policy
controls when a bounded evidence package is created; the AI gateway then evaluates
that package and publishes a versioned `iot.ai_enriched` event.

The default policy is intentionally conservative:

- scheduled reports are enabled with a one-hour interval;
- the supported interval is 10 minutes to one day;
- anomaly reports are disabled by default;
- anomaly reports require a configurable sustained condition, defaulting to 20
  seconds, and default to critical severity;
- replay events do not trigger reports unless an operator explicitly requests a
  report.

The policy does not store credentials or prompt secrets. It stores references and
version identifiers only. Authentication and authorization remain deployment-owned.

## Durable job boundary

`ai_report_jobs` is a small control-plane queue in the existing Timescale/Postgres
database. A job records its site, trigger, bounded time window, policy snapshot,
attempt count, and status. The AI gateway records a job before acknowledging the
corresponding Kafka work. Failed jobs remain retryable and are not silently lost.

Reports are built from bounded historian aggregations and samples, not from an
unbounded in-memory buffer. This keeps the normal event path fast and makes a
restart recoverable.

## Compatibility

The existing `iot.processed` and `iot.ai_enriched` topics remain unchanged as
integration points. New report metadata is additive. Existing 5-second and
100-event environment variables are retained as deprecated compatibility settings;
they no longer define governed report scheduling when a reporting policy is active.

## Acceptance criteria

1. Policy validation rejects intervals outside 10 minutes to one day.
2. API and gateway use the same persisted policy.
3. Job creation is idempotent for a site, trigger, and window.
4. Replay is excluded by default.
5. Existing AI provider fallback behavior remains available.
6. Unit and contract tests cover policy validation and job lifecycle without a
   running Kafka or LLM service.

## API

The additive API is available under `/api/v1/ai`:

- `GET /reporting-policy?site_id=*` reads the effective policy.
- `PUT /reporting-policy?site_id=<site>` replaces the validated policy.
- `GET /reporting-status?site_id=<site>` exposes bounds and effective defaults.
- `GET /reports?site_id=<site>&limit=50` lists durable report jobs.
- `POST /reports/generate` creates a manual, scheduled, or anomaly job. It does
  not execute an action or bypass the model provider boundary.

The current gateway processes scheduled evidence when the policy interval elapses
and records the job before acknowledging the Kafka output. A future worker can
claim pending jobs for retry without changing these public records.

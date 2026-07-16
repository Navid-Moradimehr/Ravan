# AI Reporting Policy and Jobs

Status: Implemented

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
unbounded in-memory buffer. Workers claim persisted jobs with database row locks
and a bounded lease. A stopped worker therefore leaves recoverable work rather
than losing an in-memory queue item. Scheduled evidence is grouped by `site_id`
before jobs are created, so one deployment serving several sites does not merge
their routine briefings.

Completed reports retain a validated `operational-briefing.v1` JSON document,
the bounded evidence IDs, provider/model metadata, prompt/cache metadata, and
delivery state. The same structured document is published to `iot.ai_enriched`
and projected into the historian. The UI renders controlled fields only; it does
not render provider-generated HTML.

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
- `GET /reports/{report_id}` returns content plus Kafka/historian delivery checks.
- `GET /reports/latest?site_id=<site>` returns the latest completed briefing.
- `GET /provider-status` returns a secret-free AI gateway readiness snapshot.
- `POST /reports/generate` creates a manual, scheduled, or anomaly job. It does
  not execute an action or bypass the model provider boundary.

The dashboard exposes same-origin proxies at `/api/ai/reporting-policy`,
`/api/ai/reporting-status`, and `/api/ai/reports`. The proxies forward a browser
bearer token when one is present. For the default self-hosted mode, mutations
work without a token; set `DATASTREAM_AUTH_REQUIRED=true` to enable the built-in
JWT boundary. This keeps the feature usable before an operator configures
AuthN/AuthZ while preserving a clean integration point for a future gateway.

The AI Reporting page also exposes the global enable flag, site scope, minimum
sample count, rearm and cooldown controls, evidence bound, replay policy, live
policy source/bounds, and durable job errors/attempts. The old `/sources` route
redirects to `/integrations#source-connections`; Integrations is the single
canonical source-management screen.

### Site scope

`site_id` is a deployment boundary, not an asset ID or tag. The AI Reporting
scope selector is populated from registered source connections and the observed
asset/tag catalog. `*` means the shared default policy. A site-specific policy
is useful when one installation hosts more than one site or report jobs must be
isolated by site.

The gateway records scheduled, sustained-anomaly, recovery, and manual evidence
as durable jobs. Independent workers claim those jobs from the database, so a
slow local model does not block Kafka polling. Deployments can set
`AI_REPORT_MAX_IN_FLIGHT` when the model server and GPU memory support safe
concurrency. The default remains conservative.

Sustained anomaly reports are evaluated independently per `site_id`, `asset_id`,
and `tag`. Three pumps can therefore produce three independent warning incidents
without one device suppressing another. The tracker requires both the configured
duration and minimum sample count, emits once per incident, excludes replay by
default, and rearms after normal recovery. The platform does not invent plant
thresholds: the deterministic processor or a user-owned mapping must assign the
event severity before the tracker evaluates it.

A failed report remains retryable, increments `attempts`, and records
`next_attempt_at` and `last_error`. A processing lease that outlives its worker is
reclaimed. After the retry limit the job remains visibly failed. If provider
fallback is enabled, the report is explicitly marked as deterministic fallback;
the provider error is preserved and shown in the report workspace. Kafka
acknowledgement and historian persistence are checked separately.

## User-visible workflow

The **Operational briefings** page is the report inbox. **Reports** displays
completed structured briefings, evidence, limitations, provider/fallback state,
and downstream delivery verification. **Activity** displays pending, processing,
retrying, and failed work. **Policy** displays provider readiness and controls
site-scoped scheduled, anomaly, and recovery behavior.

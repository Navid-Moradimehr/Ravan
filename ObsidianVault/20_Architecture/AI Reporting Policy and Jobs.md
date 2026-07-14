# AI Reporting Policy and Jobs

## Decision

AI summaries become a governed, durable consumer path. We keep the AI gateway and
Kafka topology, but move trigger policy and retry state into the existing database
control plane. No new microservice is introduced.

## Runtime contract

```text
processed events -> policy evaluation -> bounded report job -> AI gateway
                                              -> iot.ai_enriched -> historian
```

The scheduled default is one hour, with a 10-minute minimum and one-day maximum.
Anomaly reports are opt-in, critical-only by default, and require sustained
evidence. Replay is excluded unless explicitly requested.

## Ownership

- Platform: policy schema, validation, durable job lifecycle, report event contract,
  metrics, and bounded evidence construction.
- User/deployment: model endpoint, credentials, site-specific interval, anomaly
  policy, retention, and authorization integration.

## Deferred

Prompt authoring, model promotion, and human approval workflows remain separate
future capabilities. This change only establishes the stable reporting boundary.

## API

The first implementation exposes policy, status, job listing, and manual job
creation under `/api/v1/ai`. The interval is validated at 10 minutes through one
day. A job is recorded before gateway output is acknowledged, while model access
and credentials remain deployment-owned.

The gateway now has a bounded sustained-anomaly tracker and durable failure
transitions. Warning or critical evidence must remain active for the configured
duration and sample count; replay is excluded by default and a report is emitted
once per incident.

[[System Architecture]]
[[Postponed Features Matrix]]

# AI Reporting Policy and Jobs

## Decision

AI summaries are a governed, durable consumer path. The existing AI gateway and
Kafka topology remain in place; trigger policy and retry state live in the
existing database control plane. No new microservice is introduced.

## Runtime contract

```text
processed events -> policy evaluation -> bounded report job -> AI gateway
                                              -> iot.ai_enriched -> historian
```

The scheduled default is one hour, with a 10-minute minimum and one-day maximum.
Anomaly reports are opt-in, critical-only by default, and require sustained
evidence. Replay is excluded unless explicitly requested.

## UI coverage

The AI Reporting page manages the site scope, global enable flag, schedule,
anomaly duration/severity, minimum samples, rearm, cooldown, evidence bound, and
replay policy. It also displays the effective policy source and bounds plus
durable job status, attempts, timestamps, and errors.

`site_id` is the deployment boundary for sources, events, historian data, and
reporting policy. It is not an asset ID or tag. The UI builds its site selector
from registered sources and the asset/tag catalog, while `*` remains the shared
default policy.

The Integrations source editor exposes edit, structural validation,
protocol-configuration JSON, field mappings JSON, and visible discovery preview
output. Credentials remain user-owned references. The Command Center should
link to Integrations rather than duplicate the editor.

The Pipeline page reads live source-health diagnostics and recent historian
events. Its stage cards are static architecture descriptions; empty or
unavailable operational data is shown explicitly.

## Ownership

- Platform: policy schema, validation, durable job lifecycle, report event contract,
  metrics, and bounded evidence construction.
- User/deployment: model endpoint, credentials, site-specific interval, anomaly
  policy, retention, and authorization integration.

## Authentication boundary

The dashboard works without a token in the default self-hosted configuration.
Set `DATASTREAM_AUTH_REQUIRED=true` to enable the built-in JWT mutation boundary.
External gateways and SSO deployments can remain the only login layer; browser
authorization headers are forwarded when present.

## Deferred

Prompt authoring, model promotion, and human approval workflows remain separate
future capabilities. This change establishes the stable reporting boundary.

[[System Architecture]]
[[Postponed Features Matrix]]

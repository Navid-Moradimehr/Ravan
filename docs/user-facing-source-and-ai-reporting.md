# Source and AI Reporting UI

## Sources

Open **Sources** from the left navigation. This page is the operational source
surface, while **Integrations** remains the catalog of optional and deployment-
configured capabilities. Save a source definition, test it, preview fields, add
canonical mappings, and then enable it. A source can be disabled without deleting
its metadata. The edge supervisor notices registry version changes and applies
them without a container restart.

The first UI surface intentionally does not ask for secret values. Users provide
credential references backed by their environment, mounted secret file, or their
own secret manager. Protocol-specific discovery and mapping remain explicit so a
network-reachable endpoint is not mistaken for valid industrial data.

## AI reporting

Open **AI reporting** to set the scheduled reporting interval and optional anomaly
policy. The UI enforces the same policy boundary as the API: scheduled intervals
are 10 minutes through one day. Reports are disabled for sustained anomalies by
default and critical severity is the default when enabled. Operators can request a
manual report, which creates a durable job; it does not perform a plant action.

The job history is the first operational view of report requests. Model endpoint,
credentials, retention, and deployment authentication remain user-owned. AI
outputs continue to flow through `iot.ai_enriched` and the historian.


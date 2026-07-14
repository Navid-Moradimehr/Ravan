# Source and AI Reporting UI

## Sources

Open **Integrations** and use the **Source connections** panel. It is the single
operational source-management surface; the former `/sources` URL redirects there
so old bookmarks remain useful. Save a source definition, test it, preview
fields, add canonical mappings, and then enable it. A source can be disabled
without deleting its metadata. The edge supervisor notices registry version
changes and applies them without a container restart.

Existing connections also expose Enable/Disable and Remove actions. Remove is a
destructive metadata operation; disabling is the safer operational pause.

The UI intentionally does not ask for secret values. Users provide credential
references backed by their environment, mounted secret file, or their own secret
manager. Protocol-specific discovery and mapping remain explicit so a
network-reachable endpoint is not mistaken for valid industrial data.

## AI reporting

Open **AI reporting** to select a site scope, load the persisted policy, set the
scheduled interval, and configure optional sustained anomaly reporting. The UI
exposes the global enable flag, minimum samples, duration, severity, rearm,
cooldown, evidence bound, and replay policy. It enforces the same interval
boundary as the API: 10 minutes through one day. Operators can request a manual
report, which creates a durable job; it does not perform a plant action.

The job history shows durable status, attempts, timestamps, and the latest error
when a request cannot be completed. Model endpoint, credentials, retention, and
deployment authentication remain user-owned. AI outputs continue to flow through
`iot.ai_enriched` and the historian.

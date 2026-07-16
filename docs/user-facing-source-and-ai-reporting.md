# Source and AI Reporting UI

## Sources

Open **Integrations** and use the **Source connections** panel. It is the single
operational source-management surface; the former `/sources` URL redirects there
so old bookmarks remain useful. Save a source definition, test it, preview
fields, add canonical mappings, and then enable it. A source can be disabled
without deleting its metadata. The edge supervisor notices registry version
changes and applies them without a container restart.

The registry list is compact by default: it shows five sources. **Show all
sources** expands the list to twenty rows per page with pagination for the
remaining sources.

Existing connections also expose Enable/Disable and Remove actions. Remove is a
retirement action that preserves the source record for audit and replacement
history; disabling is the safer operational pause.

Existing connections can also be edited and structurally validated in the same
panel. The editor guides users through Identity, Connectivity, Discover/sample,
Map data, and Review/enable. Runtime protocols expose normal fields for MQTT
topics, OPC UA nodes, Modbus registers, RTU settings, and REST JSON paths.
Advanced JSON remains only for reference-only workflows. The mapping table maps
source fields to canonical asset/tag fields. **Validate** checks the definition
and activation readiness; **Test** is the separate network diagnostic;
**Preview** shows protocol metadata when discovery is supported; and **Enable**
activates the source.
Preview output is displayed in the panel rather than being discarded in a
toast. Secret values remain outside the platform and are referenced through
`credential_refs`, using `env://`, `file://`, `path://`, or an operator-provided
`secret://` integration.

When a source is retired, the UI keeps the record visible with an archived
state badge. You can restore it later if the same logical connection should
return to service.

### Landing-page source management recommendation

The Command Center should not contain a second source editor. The recommended
landing-page addition is a compact **Source operations** card showing the
number of registered sources, enabled/error counts, and the latest health
summary, with a **Manage sources** link to
`/integrations#source-connections`. Integrations remains the canonical editor;
this avoids conflicting state and works both before and after an operator adds
AuthN/AuthZ. A protocol-specific wizard can be added inside Integrations later
if JSON configuration becomes too advanced for a particular user group.

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

The site selector is not an asset selector. It combines site IDs known by source
registry and asset/tag metadata, and falls back to the shared `*` scope when a
deployment has not registered site metadata yet.

For cloud and local model setup, see
[`ai-provider-configuration.md`](ai-provider-configuration.md). The AI
Reporting page shows durable job state; generated content is emitted to
`iot.ai_enriched` and stored in the historian `ai_enriched` table.

## Pipeline page data contract

The Pipeline page reads source health from
`GET /api/v1/observability/source-health` and recent records from the
`industrial_events` historian table. It no longer displays invented simulator
rates, endpoints, or example events. Static stage cards describe architecture;
the ingress and event-preview panels are live when their services are available
and show an explicit empty/error state otherwise.

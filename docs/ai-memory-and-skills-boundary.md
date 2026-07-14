# AI Memory and Skills Boundary

## What the platform provides

The platform provides the durable facts and contracts an external agent needs:

- historical telemetry, alarms, and AI-enriched events in the historian;
- semantic asset and relationship metadata;
- operational-memory records for alerts, annotations, reports, and operator
  context where configured;
- versioned model and prompt registry entries;
- dataset identity, replay metadata, policy snapshots, and lineage fields;
- bounded read-only retrieval and report-job APIs;
- Kafka events with source IDs, site/asset/tag identity, model ID, prompt version,
  report ID, trigger reason, and fallback state.

This is platform memory, not an autonomous agent memory implementation. It lets a
user build episodic, semantic, or vector memory outside the core without losing
the identity and provenance needed to join the result back to industrial data.

## What users own

Users own the content and behavior of their agents:

- skill files for analysis, reporting, diagnosis, or maintenance;
- system prompts and company-specific terminology;
- memory retrieval policy, summarization policy, and vector index;
- MCP servers, tool permissions, model routing, and approval workflows;
- retention, redaction, and site-specific data-sharing policy.

A skill should identify its input contract, allowed tools, output schema, model
requirements, and version. The platform can store the version and lineage as
metadata, but it should not execute arbitrary skill files in the core service.
Mount user skill packs or connect them through an external agent runtime.

## Multiple warnings and devices

The sustained-anomaly tracker is keyed by site, asset, and tag. Warning streams
from separate PLCs and sensors are therefore independent. An event must already
contain a deterministic severity from the processing/rule layer. This avoids
asking an LLM to decide whether a raw value is dangerous and allows users to
configure different thresholds, hysteresis, deadbands, quality rules, and units
per asset in their site configuration.

When several devices qualify at once, each incident creates its own bounded
evidence set and report job. The queue limits total AI work; Kafka remains the
durable buffer. Operators should increase partitions and worker capacity only
after measuring consumer lag, model latency, GPU utilization, and queue depth.

## Recommended external agent flow

1. Consume `iot.ai_enriched` or read the governed report API.
2. Retrieve historical evidence by site, asset, tag, and time window.
3. Join semantic and operational memory using the stable IDs and lineage fields.
4. Apply the user-owned skill and model outside the core.
5. Publish the result back as a versioned user-defined AI event or store it in a
   user-owned vector/document store.
6. Keep the platform report ID, dataset ID, prompt/skill version, and model
   version in the result for audit and replay.

## Dashboard and chart status

The platform has a useful operational surface, but it does not yet have a fully
managed, shared, metadata-driven live dashboard comparable to Grafana or a BI
product. The current strengths are live historian streams, bounded trend reads,
the local custom dashboard builder, and Grafana integration. The custom builder
is browser-persisted and user-editable; Grafana is the shared/advanced dashboard
option. A future dashboard registry should be added only when shared ownership,
server persistence, or cross-site templates become a measured requirement.

Chart quality improvements already include explicit axes, bounded trend queries,
searchable selectors, null-safe rendering, responsive charts, and thinner line
strokes. Remaining work is visual consistency across every chart and a first-
class live dashboard workspace, not another processing service.

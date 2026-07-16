# AI Memory and Skills Boundary

The platform owns durable industrial facts, semantic identity, report jobs,
prompt/model/dataset metadata, lineage, and versioned AI events. Users own agent
skills, system prompts, MCP servers, vector memory, retrieval policy, and action
approval logic. The core exposes stable read-only contracts and does not execute
arbitrary skill files.

Sustained warnings are isolated by `site_id`, `asset_id`, and `tag`. Multiple
PLCs and sensors can report incidents concurrently. Plant thresholds and
hysteresis remain user-owned deterministic processing configuration; the LLM is
not the threshold engine.

AI reports run through a durable database job boundary and leased workers outside
the Kafka polling loop. `AI_REPORT_MAX_IN_FLIGHT` controls model concurrency;
there is no second authoritative in-memory report queue. Kafka remains the event
buffer and the report job remains the audit record. Prometheus exposes active
workers and job outcome counters so concurrent PLC/sensor warnings can be
capacity-managed.

The short AI memory is deliberately bounded to recent completed briefings and
evidence IDs. It supports continuity such as new, ongoing, worsening, and
resolved conditions without becoming a plant knowledge base. User skills,
long-term vector memory, action tools, and company-specific analysis policy stay
outside the core.

The UI verifies provider response, deterministic fallback, Kafka acknowledgement,
and historian projection as separate states. Scheduled reports are split by site;
anomaly and recovery state remains keyed by site, asset, and tag.

Dashboard status: historian live streams, bounded trends, the browser-persisted
custom dashboard, and Grafana integration exist. A shared server-persisted
dashboard registry and fully metadata-driven live workspace remain future work.

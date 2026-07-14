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

AI reports now run through a bounded queue and worker outside the Kafka polling
loop. `AI_REPORT_QUEUE_SIZE` and `AI_REPORT_MAX_IN_FLIGHT` are deployment knobs.
Kafka remains the durable buffer and the report job remains the audit record.
Prometheus exposes queue depth, active workers, and job outcome counters so
concurrent PLC/sensor warnings can be capacity-managed.

Dashboard status: historian live streams, bounded trends, the browser-persisted
custom dashboard, and Grafana integration exist. A shared server-persisted
dashboard registry and fully metadata-driven live workspace remain future work.

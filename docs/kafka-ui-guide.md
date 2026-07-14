# Kafka UI Guide

Kafka UI is the broker console for this platform. It is the place where you inspect Kafka itself: which topics exist, whether messages are arriving, whether consumer groups are keeping up, and whether the stream is healthy. It is not where you configure business logic, historian tables, or dashboards. It sits one layer below those things and lets you verify that the message backbone is doing its job.

The Command Center now exposes a small `?` help tip next to the Kafka UI operator link. That help tip gives the short explanation without adding a separate panel to the landing page.

Use Kafka UI when you want to:

- confirm that ingestion is producing records
- inspect a topic before and after normalization
- check whether a consumer group is lagging
- verify partitioning and offsets for throughput troubleshooting
- inspect message keys and payloads to understand the shape of the stream

In this local stack the UI is intentionally read-only. That keeps the broker console aligned with the rest of the open-source release: inspect the broker, do not change the platform from there.

When you open Kafka UI, the first thing to look at is the topic list. In this platform the canonical topics are the main contract surface. `industrial.raw` shows the pre-normalized industrial stream, `industrial.normalized` is the canonical downstream stream, `industrial.dlq` contains rejected records, `iot.raw` feeds the compatibility path, `iot.processed` contains scored events, and `iot.ai_enriched` contains AI output events. If a topic is empty, that usually means the simulator, ingestion path, or processor is not producing data yet.

Kafka UI becomes useful when you want to answer simple operational questions without reading code. You can open a topic and inspect its messages to confirm the key, value, timestamp, partition, and offset. You can check consumer groups to see whether the processor or fan-out consumers are keeping up. You can also look at topic settings to understand whether the topic exists with the expected partitioning and retention behavior. In practice, this is how operators verify that the pipeline is moving rather than stalled.

For day-to-day use, start with the live streams first. Open `industrial.raw` to confirm ingestion, then `industrial.normalized` to confirm normalization, and then `iot.processed` or `iot.ai_enriched` if you want to see how the downstream services are behaving. If the data is not there, Kafka UI helps you narrow the problem to the ingest side, the processor side, or the consumer side.

The `Create new topic` page is for provisioning a brand-new Kafka topic when you need a stream contract that does not already exist. Use it when you are introducing a new data domain, adding a replay or benchmark topic, or creating a temporary test topic in a development deployment. In the open-source local stack this page is usually not the normal operator path because topic provisioning is treated as deployment-owned infrastructure. In practice, the topic name should be chosen first, then the partition count and replication factor should match the expected throughput and resilience profile, and finally any retention or cleanup policy should match the data lifecycle you want. For industrial usage, treat a new topic as part of the platform contract, not as an ad hoc dashboard action.

The broker metrics page is now wired to the local broker's JMX endpoint. In the compose stack the Kafka broker exposes JMX on port `9997` and Kafka UI is configured to read broker metrics from that endpoint. That is what keeps the broker metrics page from falling back to an empty response and causing a browser JSON parse error. If you rebuild the stack and the metrics page is still empty, the first thing to check is whether the broker container started with the JMX options and whether port `19097` is reachable from the host.

The topic statistics page can still emit browser-console warnings in some local setups. That is usually Kafka UI trying to query ACL or analysis-related endpoints that are not fully available in a simple standalone broker install. In this repository those logs are not evidence that the platform is broken. They are a sign that Kafka UI is probing features that belong to a more permissioned or enterprise-style broker deployment. The local compose file now runs Kafka UI in read-only mode, so the broker console is intentionally diagnostic only. If you need those pages to be completely quiet, the next step is to tune Kafka UI permissions or run it against a broker that exposes the relevant ACL and analysis features.

For this project, Kafka UI should be treated as a diagnostic viewer. It gives you visibility into the event backbone, but the actual platform behavior still lives in the ingest, processing, historian, and observability services.

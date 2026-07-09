# Kafka UI Guide

Kafka UI is the broker console for this platform. It is the place where you inspect Kafka itself: which topics exist, whether messages are arriving, whether consumer groups are keeping up, and whether the stream is healthy. It is not where you configure business logic, historian tables, or dashboards. It sits one layer below those things and lets you verify that the message backbone is doing its job.

When you open Kafka UI, the first thing to look at is the topic list. In this platform the canonical topics are the main contract surface. `industrial.raw` shows the pre-normalized industrial stream, `industrial.normalized` is the canonical downstream stream, `industrial.dlq` contains rejected records, `iot.raw` feeds the compatibility path, `iot.processed` contains scored events, and `iot.ai_enriched` contains AI output events. If a topic is empty, that usually means the simulator, ingestion path, or processor is not producing data yet.

Kafka UI becomes useful when you want to answer simple operational questions without reading code. You can open a topic and inspect its messages to confirm the key, value, timestamp, partition, and offset. You can check consumer groups to see whether the processor or fan-out consumers are keeping up. You can also look at topic settings to understand whether the topic exists with the expected partitioning and retention behavior. In practice, this is how operators verify that the pipeline is moving rather than stalled.

For day-to-day use, start with the live streams first. Open `industrial.raw` to confirm ingestion, then `industrial.normalized` to confirm normalization, and then `iot.processed` or `iot.ai_enriched` if you want to see how the downstream services are behaving. If the data is not there, Kafka UI helps you narrow the problem to the ingest side, the processor side, or the consumer side.

The topic statistics page can emit browser-console warnings in a local setup. That is usually Kafka UI trying to query ACL or analysis-related endpoints that are not fully available in a simple standalone broker install. In this repository those logs are not evidence that the platform is broken. They are a sign that Kafka UI is probing features that belong to a more permissioned or enterprise-style broker deployment. If you need those pages to be completely quiet, the next step is to tune Kafka UI permissions or run it against a broker that exposes the relevant ACL and analysis features.

For this project, Kafka UI should be treated as a diagnostic viewer. It gives you visibility into the event backbone, but the actual platform behavior still lives in the ingest, processing, historian, and observability services.


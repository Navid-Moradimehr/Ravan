# Kafka UI Guide

Kafka UI is the broker console for the platform. It is where you inspect Kafka topics, consumer groups, partitions, offsets, and message payloads. It does not configure the application logic itself. It helps users verify that the event backbone is healthy.

In the local compose stack it is set to read-only mode so users inspect the broker without mutating it from the console.

The main topics to check are `industrial.raw`, `industrial.normalized`, `industrial.dlq`, `iot.raw`, `iot.processed`, and `iot.ai_enriched`. If `industrial.raw` is active, ingress is working. If `industrial.normalized` is active, the canonical event path is working. If `iot.processed` and `iot.ai_enriched` are active, the downstream processing and AI paths are working too.

Kafka UI is most useful when you want to troubleshoot the stream without reading service logs. You can open a topic to see messages, inspect the offset progression, and check consumer groups to see whether the processor is lagging. That tells you where the pipeline is healthy and where it is not.

The topic statistics page may show browser-console warnings in this local setup. Those warnings usually come from Kafka UI trying to call ACL or analysis endpoints that are not fully available in a simple standalone broker environment. For this project that means the console is probing features that belong to a more permissioned Kafka installation. The platform itself is still fine if the core topics and consumer groups are working.

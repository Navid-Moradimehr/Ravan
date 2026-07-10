# Kafka UI Guide

Kafka UI is the broker console for the platform. It is where you inspect Kafka topics, consumer groups, partitions, offsets, and message payloads. It does not configure the application logic itself. It helps users verify that the event backbone is healthy.

The Command Center now places the Kafka UI explanation as a small `?` help tip next to the Kafka UI operator link instead of using a separate help panel.

In the local compose stack it is set to read-only mode so users inspect the broker without mutating it from the console.

The main topics to check are `industrial.raw`, `industrial.normalized`, `industrial.dlq`, `iot.raw`, `iot.processed`, and `iot.ai_enriched`. If `industrial.raw` is active, ingress is working. If `industrial.normalized` is active, the canonical event path is working. If `iot.processed` and `iot.ai_enriched` are active, the downstream processing and AI paths are working too.

Kafka UI is most useful when you want to troubleshoot the stream without reading service logs. You can open a topic to see messages, inspect the offset progression, and check consumer groups to see whether the processor is lagging. That tells you where the pipeline is healthy and where it is not.

The `Create new topic` page is for provisioning a new Kafka topic when the stream contract does not already exist. Use it when you are adding a new data domain, creating a replay or benchmark topic, or standing up a temporary test stream in a development deployment. In the open-source local stack this is not the normal day-to-day operator path because topic provisioning is usually deployment-owned infrastructure.

The topic statistics page may show browser-console warnings in this local setup. Those warnings usually come from Kafka UI trying to call ACL or analysis endpoints that are not fully available in a simple standalone broker environment. For this project that means the console is probing features that belong to a more permissioned Kafka installation. The platform itself is still fine if the core topics and consumer groups are working.

Kafka UI itself is an upstream web application running in Docker Compose. This repository controls the container, links, and explanatory text, but the actual Kafka UI page is owned by the upstream project.

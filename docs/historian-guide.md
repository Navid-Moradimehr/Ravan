# Historian Guide

The historian is the platform's long-term memory. It stores the normalized and processed events so users can ask what happened after the live stream has moved on. If Kafka is the transport backbone, the historian is the place where historical readback happens.

When a user opens the historian page, they are looking at the storage and recovery surface of the platform. The dashboard at the top gives a quick read on historical trends and operational state. The SQL query panel is for asking direct questions against the historian tables. The replay controls are for re-running a stored dataset or scenario. The webhook and notification panels are for connecting historian events to external systems.

If you are new to the page, start with the dashboard and trend views. Those are the easiest way to see what the stored data looks like. If you need a custom question, use the SQL panel. That panel is read-only and is meant for analysis, not for changing data. If you need to repeat a simulation or validate a change, use replay. If you want historian output to trigger another system, use webhooks or notifications.

The historian is intentionally after storage, not part of the raw ingest path. That matters because it keeps the live pipeline simple: Kafka carries the stream, processing services score it, and the historian stores the result for later use. Users should think of this page as the answer to “what happened?” rather than “how do I ingest data?”


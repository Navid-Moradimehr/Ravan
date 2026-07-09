# Historian Guide

The historian is the storage and readback surface of the platform. It stores normalized and processed events so users can ask what happened after live ingestion has already passed through Kafka and processing.

The historian page is where you inspect trends, run SQL, replay a stored dataset, and connect the stored events to external systems through webhooks or notifications.

How to use it:

1. Open the historian dashboard first.
2. Use SQL when you need a custom read-only query.
3. Use replay when you want to re-run a dataset or scenario.
4. Use webhooks and notifications when you want historian events to leave the platform.

Important:

- the historian is not the ingest front door
- it answers “what happened?”
- Kafka UI answers “did the event move through the broker?”


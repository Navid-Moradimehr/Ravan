# Historian Guide

The historian is the storage and readback surface of the platform. It stores normalized and processed events so users can ask what happened after live ingestion has already passed through Kafka and processing.

The historian page is where you inspect trends, run SQL, replay a stored dataset, and connect the stored events to external systems through webhooks or notifications.

The `Alarms & Events` and `Raw Events` panels stay compact by default so the page does not become unreadable as data grows. Each panel shows the latest five rows first, then expands to the full list on demand. Both panels also expose a refresh selector so operators can slow down, pause, or speed up the backend polling cadence when they are reviewing a busy stream, and the selected cadence is remembered in the browser after reload.

The SQL panel also remembers the last query text, saved query snippets, and timeout value in the browser. The cancel button stays transient because it only applies to the currently running statement.

How to use it:

1. Open the historian dashboard first.
2. Use SQL when you need a custom read-only query.
3. Use replay when you want to re-run a dataset or scenario.
4. Use webhooks and notifications when you want historian events to leave the platform.

Important:

- the historian is not the ingest front door
- it answers "what happened?"
- Kafka UI answers "did the event move through the broker?"
- the live historian panels are fed by the API service through HTTP polling from the browser
- the alarms panel asks the backend for alarm history at the chosen interval
- the raw events panel asks for the selected historian table at the chosen interval

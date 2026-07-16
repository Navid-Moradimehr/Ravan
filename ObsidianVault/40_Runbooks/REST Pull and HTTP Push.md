# REST Pull and HTTP Push

## Current status

Implemented in the connection registry, edge runtime, and API service. No new
container is required.

## REST Pull

1. Open **Integrations** and choose **REST Pull**.
2. Enter an HTTP(S) URL, method, interval, timeout, and optional bounded
   pagination.
3. Configure dotted JSON paths for `asset_id`, `tag`, and `value`; `source_id`,
   timestamp, quality, and unit paths are also supported.
4. Add only credential references. The runtime supports none, basic, bearer,
   API key, OAuth2 client credentials, and mTLS configuration contracts.
5. Save the draft, Validate, Test, and Enable.

The connector polls without writing to the historian directly. Every record is
converted to the canonical event model, receives a deterministic event ID,
publishes through Kafka, and then follows the normal processor/Flink,
historian, DLQ, lineage, and optional sink path. Retries, pages, records per
poll, timeout, and response size are bounded.

## HTTP Push

1. Create an **HTTP Push** connection with a site and source identity.
2. Save and enable it. The platform does not require an external endpoint
   because it owns the receiving route.
3. Post one event to
   `/api/v1/connections/<connection_id>/events`, or up to 1,000 events to
   `/api/v1/connections/<connection_id>/events/batch`.
4. Include `event_id` or `Idempotency-Key` when the upstream may retry.

HTTP Push requires a registered enabled connection, stamps connection/site
lineage, and reuses the canonical ingest path. Authentication, TLS exposure,
rate limits, and user authorization remain the operator's reverse-proxy/API
security boundary. The in-process idempotency cache is bounded and is not a
substitute for durable deduplication in a multi-replica deployment.

## Boundaries

The platform owns the contract and event path. Users own endpoint correctness,
API semantics, secrets, TLS trust, rate limits, and whether their gateway sends
raw or already-normalized fields. File, dataset, and mock remain reference-only
source definitions in this release.

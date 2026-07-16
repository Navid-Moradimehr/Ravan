# API Gateway and Route Contract

The platform has two HTTP service boundaries, not one hidden cloud gateway.
The FastAPI API service on port `8020` is the application gateway for historian,
metadata, connections, processing, alerts, semantic, retrieval, and admin
contracts. The AI gateway on port `8080` owns model telemetry, AI events, and
AI-specific streaming. Kafka remains the event backbone between processing and
AI; the dashboard does not bypass Kafka to read industrial data.

The Next.js dashboard exposes same-origin `/api/*` routes. These are thin
server-side proxies to the FastAPI service, which keeps browser requests from
depending on Docker DNS names. The Docker `ui` profile now starts
`api-service` and waits for it to start, so dashboard requests such as
`/api/historian`, `/api/query`, `/api/kpis`, `/api/connections`,
`/api/webhooks`, and `/api/notifications` have a reachable backend.

The proxy surface covers the editable UI operations:

- Historian reads, bounded SQL query submission, and query cancellation
- KPI list/create/delete
- Connection list/create/get/update/delete and enable/disable/validate/test/preview
- Webhook list/create/delete/test
- Notification list/create/delete
- HTTP Push single-event and bounded batch ingress at
  `/api/v1/connections/<connection_id>/events` and
  `/api/v1/connections/<connection_id>/events/batch`
- Observability, federation, and source-health snapshots
- Source delivery history at `/api/v1/observability/source-delivery`
  - Returns bounded recent delivery attempts from HTTP Push and edge REST connectors; failures include a short actionable error and attempt count.
- OPC UA browse selection persistence at `/api/v1/connections/{connection_id}/opcua/browse-selection`
  - Accepts up to 500 node IDs, deduplicates them, and saves them as the next connector node set without storing certificates or keys.

Historian browser clients should use the canonical same-origin query form
`/api/historian?action=events|trend|assets|scenarios|alarms|replay`. For
backward compatibility with cached or older browser bundles, the dashboard also
accepts legacy path aliases such as `/api/historian/assets`,
`/api/historian/scenarios`, and `/api/historian/replay` and forwards them to
the same backend historian contracts.

Authorization headers are forwarded on mutation proxies. No identity provider,
token issuer, RBAC model, or reverse proxy is imposed by the project. The built-in
JWT middleware is opt-in: set `DATASTREAM_AUTH_REQUIRED=true` when the operator
wants the API to reject unauthenticated mutations. The default is `false` so a
self-hosted installation can rely on its own network boundary, reverse proxy, or
SSO layer without a second login. Operators may place their chosen authentication
system in front of the dashboard and API.

For a Docker dashboard deployment, use:

```text
docker compose -f docker/docker-compose.yml --profile ui up -d
```

For a separately run dashboard, set `API_SERVICE_BASE` to the reachable API
URL. The default `http://localhost:8020` is appropriate when Next.js runs on
the host; Docker overrides it with `http://api-service:8020`.

The KPI Builder must use the dashboard proxy routes (`/api/kpis` and
`/api/kpis/<id>`), not FastAPI paths directly from browser code. This keeps
KPI operations on the same forwarding and error-handling path as the other
editable UI features. The production build verifies that these proxy routes
are present.

The API WebSocket endpoints are `/ws/alarms`, `/ws/events`, and
`/ws/telemetry`. Their browser base URL is configured with
`NEXT_PUBLIC_API_WS_BASE_URL`; the Compose UI profile sets it to
`ws://localhost:8020`. Deployments that expose the dashboard and API through
another host or TLS terminator must set this value to the externally reachable
`ws://` or `wss://` URL. The API service still owns the WebSocket routes; the
AI gateway is used for AI telemetry data, not as the WebSocket host.

HTTP Push is intentionally an API-service ingress, not a browser dashboard
proxy. A gateway, PLC bridge, or user-owned application posts to the API
service on port `8020` after an `http_push` connection is enabled. The API
stamps the registered site/source identity and sends the event through the
same canonical validation, Kafka, DLQ, processing, and historian path as
other sources. The single-process idempotency cache is bounded and suitable
for one-node Compose deployments; multi-replica deployments must put a
durable/shared idempotency boundary in front of the API.

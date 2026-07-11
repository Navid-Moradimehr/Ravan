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
- Observability, federation, and source-health snapshots

Authorization headers are forwarded on mutation proxies. No identity provider,
token issuer, RBAC model, or reverse proxy is imposed by the project; operators
may place their chosen authentication system in front of the dashboard and API.

For a Docker dashboard deployment, use:

```text
docker compose -f docker/docker-compose.yml --profile ui up -d
```

For a separately run dashboard, set `API_SERVICE_BASE` to the reachable API
URL. The default `http://localhost:8020` is appropriate when Next.js runs on
the host; Docker overrides it with `http://api-service:8020`.

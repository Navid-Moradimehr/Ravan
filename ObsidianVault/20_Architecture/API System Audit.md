# API System Audit (2026-07-13)\n\n**Status: route wiring verified; browser proxy and source-ingress contracts applied.**

## 2026-07-13 Verification

- FastAPI imports successfully and exposes 128 OpenAPI paths, including the
  historian, metadata, connection, KPI, webhook, notification, observability,
  semantic, retrieval, and replay contracts.
- The dashboard production build exposes the expected same-origin proxy routes
  under `/api/*`.
- Added a legacy-compatible historian alias route so older browser bundles that
  still call `/api/historian/assets`, `/api/historian/scenarios`, or
  `/api/historian/replay` are forwarded to the canonical historian contract
  instead of surfacing 404s.
- Fixed the KPI Builder, which had called `/api/v1/kpis` directly from browser
  code even though its Next.js proxy is `/api/kpis`. KPI list, create, and
  delete now use the proxy and encode KPI identifiers.
- WebSocket clients now read `NEXT_PUBLIC_API_WS_BASE_URL` instead of baking
  `ws://localhost:8020` into the client library. Compose sets the local value;
  installed deployments can set an externally reachable `ws://` or `wss://`
  endpoint.
- Static scans found no remaining client-component calls that bypass the
  same-origin proxy with `/api/v1/*`.
- HTTP Push single and batch ingress routes are mounted on the API service and
  use the registered connection lifecycle before entering canonical ingest.
- REST Pull preserves the external record on the raw Kafka topic while the
  normalized topic receives only the canonical industrial event.
- Container HTTP verification was not possible in this pass because Docker
  Desktop was unavailable (`dockerDesktopLinuxEngine` pipe missing). The
  FastAPI route contract tests passed and the UI production build passed.

## 2026-07-16 Verification

- Rebuilt `api-service`, `edge-ingest`, and `dashboard` from the current tree
  with Docker Desktop.
- `GET /health`, the dashboard Integrations page, Kafka UI, Grafana proxy, and
  Prometheus readiness all returned HTTP 200.
- HTTP Push was exercised through the live API: a registered enabled source
  accepted a canonical event, repeated `Idempotency-Key` delivery returned a
  duplicate, and the source was retired cleanly.
- Playwright loaded `/integrations` with zero console errors; source, health,
  threshold, update, and navigation requests returned HTTP 200.
- The 2026-07-13 Docker limitation above is historical and superseded by this
  verification.

## Findings

### Connectivity / wiring
- All routers are reachable: 8 sub-routers (connectors, digital_twin, oee,
  pipelines, preview, schemas, backup, reports) are mounted via `design` and
  `support` parent routers, which are included in `main.py`. Not orphaned.
- API -> AI gateway telemetry uses an **in-process import**
  (`from services.ai_gateway.main import _build_telemetry`) inside
  `realtime._telemetry_broadcaster`. This reuses the function inside the API
  process rather than calling the running AI gateway over HTTP. Works only
  because both images ship the full `services/` tree.

### Duplicate logic
- **Historian REST API duplicated** across two services: the AI gateway exposes
  `/historian/{events,trend,assets,scenarios,alarms,replay,stream}` with no auth,
  overlapping the API service's `/api/v1/historian/*` router (which IS gated).
- **API ingest dual-writes**: `runtime._do_ingest_event` writes to the historian
  AND publishes to Kafka. With the Phase-3 fan-out consumer now also persisting
  `industrial.normalized`, API-ingested events are written twice (dedup'd by the
  event_id unique index, but still wasted work).
- Two Kafka publish helpers in `runtime.py`: `_publish_kafka` (cached producer)
  and `_publish_kafka_fresh` (new producer per call) - duplicate logic.

### Bugs
- `service_state["running"]` (item access) at `ai_gateway/main.py:120` and `:222`
  will raise `TypeError` because `ServiceHealthState` is a dataclass with no
  `__getitem__`. The SSE `/events` and `/historian/stream` endpoints crash on
  first client connection.

### Gating / authz
- Global middleware only gates POST/PUT/PATCH/DELETE and only verifies the
  bearer token is valid - no role/permission check. All GET is ungated.
- Only `admin.py` uses `require_permission`; everything else is token-presence.

### Health check
- `/health` hardcodes `historian/kafka/ai_gateway = True` instead of probing.

### Protocol usage
- Edge protocols are correct: MQTT (paho pub/sub), OPC UA (asyncua), Modbus
  (pymodbus TCP). Webhook notifications use HTTP POST + retry/backoff (good).
- Real-time delivered via two mechanisms: WebSocket (`/ws/*`, API) and SSE
  (`/events`, `/historian/stream`, AI gateway). The SSE ones are broken by the
  bug above.

## Recommended fixes (priority order)
1. ~~Fix `service_state["running"]` -> `service_state.running`~~ DONE (2026-07-06).
2. Remove AI gateway's duplicate `/historian/*` REST surface (or gate it).
3. ~~Remove the direct historian write from `runtime._do_ingest_event`~~ DONE (2026-07-06).
4. ~~Consolidate `_publish_kafka` / `_publish_kafka_fresh`~~ DONE (2026-07-06).
5. Make `/health` probe real dependencies.
6. (Authz) Out of scope per current constraints, but GET reads of sensitive data are open.

## Test-drift reconciliation (2026-07-06)

A full-suite run found nine tests that drifted from earlier refactors. All
reconciled; full suite now 419 passed.

- **TLS tests** pointed at `edge_ingest/main.py` after the connector split
  (commit 75e4b89) moved TLS wiring into `connectors/{mqtt,opcua,modbus}.py`.
  Tests now read the connector modules.
- **Historian tests** had `execute_values` mocks with the old positional
  signature; the batch refactor added a `page_size` kwarg. Mocks updated.
- **AI gateway test** used dict-style `service_state["..."]` access. Switched to
  the `ServiceHealthState` object API.
- **UI mobile tests** asserted a literal `width=device-width` meta string and
  `lg:grid-cols-` classes; the UI uses the Next.js 14 `viewport` export and
  `sm:`/`md:`/`xl:` breakpoints. Assertions relaxed to match.
- **DLQ ingest test** failed only in the full suite due to two leaks:
  `test_historian` set `TIMESCALE_HOST` via `os.environ` (now `monkeypatch.setenv`)
  and `_get_producer` is `@lru_cache`d so a prior test's fake producer stayed
  cached (the test now calls `cache_clear()`).

### Bug found and fixed during reconciliation
- `enrich_batch` marked the AI gateway degraded when the LLM fell back to a
  deterministic summary, then unconditionally called `service_state.mark_ok()`
  at the end of the happy path, silently clearing the degraded state. Added a
  `used_fallback` guard so `mark_ok()` only runs when the LLM actually succeeded.
  This is the only production-code change in this pass; it preserves the
  degraded signal operators rely on.
## 2026-07-16 Source hardening evidence

- HTTP Push idempotency is now durable in the TimescaleDB `http_push_idempotency` table and fails closed with `503` if the ledger cannot be consulted.
- Source delivery history is bounded and persistent. Compose merges API-origin records from `/data` with edge connector records from the shared edge volume at `/api/v1/observability/source-delivery`.
- Modbus TCP and RTU use the same typed register contract for datatype, scaling, byte order, and word order; legacy RTU `address:count` maps remain accepted.
- OPC UA supports security-string execution hooks and bounded browse previews. Certificate/trust-store lifecycle management remains operator-owned and is not claimed as complete.
- OPC UA selected node IDs can be persisted through a bounded API contract without exposing certificate or key material.
- Sparkplug B birth/death lifecycle topics now update source health and emit canonical state events; command/rebirth orchestration remains outside the core connector.
- The edge validates OPC UA signed certificate validity and private-key readability without provisioning or exposing trust material. Sparkplug rebirth is an explicit opt-in using the Tahu payload builder; vendor-specific gateways remain outside the core protocol contract.

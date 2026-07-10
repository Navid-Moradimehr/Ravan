# Command Center Walkthrough

This page is the landing surface for the platform. It is not a data-entry screen. It is a control-room overview that helps a user decide where to go next.

## What the page shows

The current Command Center has five parts:

1. Hero section
2. Execution lanes
3. Live pipeline summary
4. Current health snapshot
5. Right-rail operator links and stack summary

The earlier `Platform indicators` block has been removed.

## 1) Hero section

The hero section gives the page its title and primary actions.

What it does:

- tells the user they are in the industrial streaming control plane
- gives two direct entry points into the deeper surfaces
- keeps the landing page readable without exposing every subsystem at once

Inputs:

- no live data
- page navigation state

Outputs:

- a concise overview header
- links to the pipeline view and historian tools

How users use it:

- first-time users can jump to the pipeline or historian quickly
- operators can use it as the fastest route into the working areas of the platform

## 2) Execution lanes

These are the route cards under Navigation.

What they do:

- `Pipeline` opens ingress, normalization, DLQ, and event preview
- `Processing` opens the stream-processing and benchmark area
- `Historian` opens SQL, backup, replay, webhooks, and dashboards
- `Observability` opens throughput, latency, reconnect, and health views

Inputs:

- route configuration in the UI

Outputs:

- navigation into the corresponding domain page

How users use it:

- users choose the area they want to inspect instead of reading the whole platform from one page

## 3) Live pipeline summary

This section shows the current pipeline stages.

What it does:

- reads the live telemetry websocket when available
- falls back to a demo pipeline state if no live telemetry has arrived yet
- shows stage-by-stage status for `edge`, `normalize`, `process`, and `ai`

Inputs:

- telemetry websocket payloads from `/ws/telemetry`
- fallback placeholder state when the stream is not yet connected

Outputs:

- visible stage cards showing status
- a source badge that tells the user whether the data is live or fallback

How users use it:

- operators can see whether the stream is active
- developers can tell if the app is using real telemetry or demo state

Important note:

- `starting` is a fallback status, not a guarantee that the real service is starting
- if the websocket has not delivered a payload yet, the page uses the placeholder pipeline

## 4) Current health snapshot

This section summarizes observability.

What it does:

- queries the observability route for Prometheus and Grafana state
- renders a compact snapshot of health and throughput
- falls back to a demo snapshot when observability services are not reachable

Inputs:

- `/api/observability`
- Prometheus query results
- Grafana health status

Outputs:

- Grafana status card
- Prometheus status card
- throughput card
- AI p95 latency card

How users use it:

- operators see whether the monitoring stack is healthy
- engineers use it to check whether the ingestion path is producing data

What throughput means:

- this is ingest throughput, measured as events per second
- it is derived from Prometheus metrics for the edge ingest stream

## 5) Right rail

The right rail contains two quick-reference panels.

### Current Stack

What it does:

- summarizes the active local stack
- shows the core runtime choices used by the platform in this environment

What it shows:

- Kafka broker
- Python + Flink processing
- LM Studio AI endpoint
- TimescaleDB storage

### Operator Links

What it does:

- gives direct access to the external tools used by the platform

Links:

- Kafka UI
- Grafana
- Prometheus
- Edge metrics
- AI health

Kafka UI note:

- the Kafka UI explanation is attached to the Kafka UI link itself as a small `?` help tip
- it is not rendered as a separate help card in the Command Center anymore
- the help tip explains that Kafka UI is the broker console and that it is a third-party web app, not a page built inside this React app

## Typical user flow

1. Open the Command Center.
2. Read the hero section to orient yourself.
3. Use an execution lane to jump into the specific subsystem.
4. Check the live pipeline summary for stream health.
5. Check the health snapshot for observability state.
6. Use the operator links if you need the broker, metrics, or AI service directly.
7. Hover the Kafka UI help tip if you want the broker-console explanation without leaving the page.

## What is live and what is fallback

Live:

- telemetry summary when `/ws/telemetry` is connected and sending payloads
- health snapshot when Prometheus and Grafana are reachable

Fallback:

- pipeline stage placeholders when telemetry has not arrived yet
- demo observability snapshot when metrics services are unavailable

## Editable vs external pages

The Command Center itself is part of this repository and is editable here.

The Kafka UI and Grafana pages that it links to are external services running in Docker Compose:

- Kafka UI is served by the `ghcr.io/kafbat/kafka-ui` container on `http://localhost:18080`
- Grafana is served by the `grafana/grafana` container and proxied on `http://localhost:13000`

That means the links, proxying, provisioning, and surrounding help text are editable in this repo, but the actual third-party UI pages are owned by their upstream projects.

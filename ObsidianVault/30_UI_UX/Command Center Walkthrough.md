# Command Center Walkthrough

The Command Center is the landing page for the platform. It is a control-room overview, not a data-entry surface.

## Current structure

- Hero section
- Execution lanes
- Live pipeline summary
- Current health snapshot
- Right-rail stack summary and operator links

The earlier `Platform indicators` block is no longer part of the page.

## Hero section

The hero section orients the user and gives two primary actions.

Purpose:

- identify the page as the industrial streaming command center
- direct users into the pipeline or historian

Inputs:

- navigation only

Outputs:

- page title
- primary CTA buttons

## Execution lanes

Purpose:

- move the user into the working pages

Routes:

- Pipeline
- Processing
- Historian
- Observability

## Live pipeline summary

Purpose:

- show stage-by-stage pipeline status

Live source:

- `/ws/telemetry`

Fallback:

- placeholder pipeline with `starting` statuses

Important:

- `starting` is a fallback label when no live telemetry has arrived yet

## Current health snapshot

Purpose:

- summarize platform observability in a compact form

Live source:

- `/api/observability`

Fallback:

- demo snapshot when Prometheus or Grafana are not reachable

Throughput:

- ingest rate in events per second from Prometheus metrics

## Right rail

Current Stack:

- Kafka
- Python + Flink
- LM Studio
- TimescaleDB

Operator Links:

- Kafka UI
- Grafana
- Prometheus
- Edge Metrics
- AI Health

Kafka UI note:

- the broker-console explanation is attached to the Kafka UI link itself as a small `?` help tip
- it is not a separate panel on the page anymore
- the help tip explains that Kafka UI is a third-party web app, not a React page built inside this repository

## User flow

1. Read the hero section.
2. Choose an execution lane.
3. Check the live pipeline summary.
4. Check the health snapshot.
5. Use the right-rail links for the broker or monitoring tools.
6. Hover the Kafka UI `?` help tip if you want the short broker-console explanation.

## Editable vs external pages

The Command Center is editable in this repository.

The Kafka UI and Grafana pages are external services provided by their upstream Docker images and proxied links:

- Kafka UI is served at `http://localhost:18080`
- Grafana is served at `http://localhost:13000`

This repo controls how they are launched, linked, and explained, but the actual pages belong to the upstream projects.

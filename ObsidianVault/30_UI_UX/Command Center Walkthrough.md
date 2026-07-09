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

## User flow

1. Read the hero section.
2. Choose an execution lane.
3. Check the live pipeline summary.
4. Check the health snapshot.
5. Use the right-rail links for the broker or monitoring tools.


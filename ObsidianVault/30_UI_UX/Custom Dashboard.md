# Custom Dashboard

## Current State

The Historian Custom Dashboard is now a functional lightweight operator view,
not a placeholder grid. It renders real data through existing platform APIs:

- Historian trend
- Historian statistics
- Alarm table
- Historian events table
- Runtime health and throughput

## Boundaries

The builder reads through the dashboard API routes. It does not bypass the API
to access Kafka or TimescaleDB directly. Grafana remains the advanced dashboard
surface for Prometheus variables, transformations, sharing, and centralized
dashboard administration.

Panel definitions are currently persisted in browser `localStorage`. This is
deliberate because authentication and multi-user identity are user-owned in the
open-source deployment model. A future metadata-backed registry can preserve
the same panel contract for shared site dashboards.

## Verification

- UI production build passes with Next.js and TypeScript.
- Panel query refresh can be paused with refresh seconds set to `0`.
- Trend panels require an explicit asset/tag from the asset registry.
- Empty and API-error states are rendered inside the panel instead of showing
  fake data.

## Future Extension

Add backend dashboard persistence only when site identity, ownership, sharing,
and permissions are configured. Do not turn the quick builder into a second
Grafana; integrate with Grafana for advanced dashboards.

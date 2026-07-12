# Custom Dashboard Guide

The Historian page contains a lightweight platform dashboard builder for
operators who need a focused view of the current site. It is intentionally
smaller than Grafana: use it for a few historian and runtime panels, and use
Grafana for advanced Prometheus queries, variables, transformations, sharing,
and multi-dashboard administration.

## What It Reads

The builder uses existing platform APIs. It does not create a second data
pipeline or read Kafka directly from the browser.

- Historian trend panels read `/api/historian?action=trend`.
- Event panels read `/api/historian?action=events`.
- Alarm panels read `/api/historian?action=alarms`.
- Statistics panels combine historian events and alarms.
- Runtime health panels read `/api/observability`, which summarizes Prometheus
  and service telemetry.
- Trend asset/tag choices come from `/api/historian?action=assets`.

## First-Time Setup

1. Start the platform and simulator stack:

   ```powershell
   docker compose -f docker/docker-compose.yml --profile edge --profile api --profile ui up -d
   ```

2. Open `http://localhost:3006/historian`.
3. Scroll to **Custom Dashboard**.
4. The default layout contains Historian overview and Latest alarms.
5. Use the gear button on a panel to configure its title, table, asset tag,
   time window, or refresh interval.
6. Use **Add panel** to add a historian trend, statistics, alarm table, events
   table, or runtime health panel.
7. Move panels with the up/down buttons or remove them with the `X` button.
8. Use **Reset layout** to restore the default two-panel layout.

## Panel Configuration

For a trend panel, select a configured asset tag and choose a time window in
hours. If the asset registry has no tags, the panel remains empty and explains
that an asset registry entry is required. This is intentional: the dashboard
does not guess a tag from arbitrary historian rows.

For an events or statistics panel, enter the historian table name. The default
is `industrial_events`. The panel samples the newest rows and refreshes them
according to its refresh setting.

For alarms and runtime health, configuration is limited to the title and
refresh interval because their APIs already define the appropriate dataset.
Set refresh seconds to `0` to pause polling.

## Persistence And Scope

The current builder saves its dashboard definition in the browser's
`localStorage`. This makes it usable without adding authentication, a new
database, or a new service. The layout is therefore local to one browser
profile and is not yet shared between operators, sites, or machines.

Grafana should be used when a dashboard must be centrally managed, shared,
versioned, or parameterized across sites. A future metadata-backed dashboard
registry can promote these same panel definitions to shared dashboards after
the platform's user and site identity model is configured.

## Troubleshooting

- Empty trend: verify the asset registry contains the selected tag and that
  the historian has received events for it.
- Empty events: verify the table name and confirm the historian sink is
  enabled with `SINKS=historian`.
- Runtime health fallback: check Prometheus at `http://localhost:19090` and
  the observability API; the page reports a degraded state instead of hiding
  unavailable telemetry.
- Browser-only layout reset: clear the dashboard's local storage or use
  **Reset layout**. This does not delete historian data.


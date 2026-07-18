# Historian Guide

The historian is the platform's long-term memory. It stores the normalized and processed events so users can ask what happened after the live stream has moved on. If Kafka is the transport backbone, the historian is the place where historical readback happens.

When a user opens the historian page, they are looking at the storage and recovery surface of the platform. The dashboard at the top gives a quick read on historical trends and operational state. The SQL query panel is for asking direct questions against the historian tables. The replay controls are for re-running a stored dataset or scenario. The webhook and notification panels are for connecting historian events to external systems.

The two live event panels stay compact by default. `Alarms & Events` and `Raw Events` both show the latest five rows first so the page stays readable as data grows. Each panel includes an expand toggle to reveal the full list when the operator wants the complete history. Both panels also expose a refresh selector so users can slow down, pause, or speed up the backend polling cadence when they are reviewing a busy stream, and the choice is remembered in the browser so it stays set after reload.

The SQL panel also remembers the last query text, saved query snippets, and timeout value in the browser. The cancel button stays transient because it only applies to the currently running statement.

If you are new to the page, start with the dashboard and trend views. Those are the easiest way to see what the stored data looks like. If you need a custom question, use the SQL panel. That panel is read-only and is meant for analysis, not for changing data. If you need to validate a change against a known dataset, use replay. If you want historian output to trigger another system, use webhooks or notifications.

When the platform sees live source traffic but no mapping match yet, the historian page also shows a short warning above the raw event table. That is a semantic-setup signal, not a historian failure: the ingest path can still be healthy while the mapping contract is not aligned with the incoming fields yet.

The historian is intentionally after storage, not part of the raw ingest path. That matters because it keeps the live pipeline simple: Kafka carries the stream, processing services score it, and the historian stores the result for later use. Users should think of this page as the answer to “what happened?” rather than “how do I ingest data?”

The live panels are fed by the API service through HTTP polling from the browser. The alarms panel asks the backend for alarm history at the chosen interval, and the raw events panel asks for the selected table at the chosen interval. The browser is not inventing data; it is rendering the current historian state coming from the backend, just on a cadence the operator can control.

The Historical Trend panel also includes an Asset tag selector. It is populated
from the registry plus the observed asset/tag catalog. Selecting a value there
or clicking a tag in Asset Hierarchy drives the same historian query. If the
selector is empty, start normalized fan-out or run the bounded catalog
reconciliation endpoint described in the threshold policy guide.

The hierarchy distinguishes configured topology from discovery. Equipment such
as pumps and motors is treated as an asset when it has tag children, even when
its type is not literally named `asset`. The `demo` marker identifies the
bundled example site. An `observed` branch contains asset/tag pairs found in
historian traffic that are not yet part of the configured registry. Observed
data is useful for discovery, but it does not invent a line, area, or cell
relationship. Add the source and topology to the asset registry when the
observed signal is ready to become part of the operational model.

The selector is searchable: type a site, asset ID, asset name, tag, or source
to narrow the candidates. The **Time span** selector controls the historian
window independently of the live refresh setting and supports the last hour,
6 hours, 24 hours, or 7 days. The selected span is remembered in the browser.
The rendered trend is a responsive line chart with a
`Time` x-axis, the selected tag and unit on the y-axis, gridlines, and a hover
tooltip. If the catalog has no unit, the tag name is used as the value-axis
label. The query includes the selected site when one is available, so two
sites can use the same asset ID without their readings being mixed. A chart's
maximize button opens a centered, non-fullscreen view with a blurred backdrop;
the transition returns to the original chart position when minimized. Escape
and the close button provide the same behavior, and reduced-motion preferences
are respected.

The default one-hour window is intentionally current-data oriented. Bundled
demo and replay samples may be older than that window, so use `Last 7 days`
when reviewing those samples. A blank chart in that case means that no rows
matched the selected site, asset, tag, and time range; it is not proof that the
historian is empty.

The Raw Events table also has a searchable selector for the supported historian
projections: `industrial_events`, `processed_events`, and `ai_enriched`. This
selection is intentionally limited to the historian API contract and does not
scan arbitrary database tables.

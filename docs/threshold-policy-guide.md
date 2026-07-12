# Threshold Policy Guide

## What the platform owns

The platform now provides a small metadata-plane threshold policy store. It
keeps the site, asset, tag, engineering unit, limit mode, warning limits,
critical limits, deadband, transition delays, enabled state, source, and policy
version. Policies are persisted in `metadata_threshold_policies`, not mixed
into the time-series rows.

The effective precedence is deterministic:

1. An explicit policy saved by the operator in the platform.
2. A policy imported from an external PLC, OPC UA, DCS, or another approved
   source, when represented in the policy store with its source recorded.
3. The configured asset manifest (`config/assets.yaml`).
4. The existing anomaly-score severity when no threshold policy is configured.

The resulting processed event records both the final severity and the threshold
decision. The fields `threshold_severity`, `threshold_status`,
`threshold_source`, `threshold_policy_version`, and `threshold_breached` make
the decision auditable. Existing anomaly scoring is not removed: the final
severity is the more severe of the anomaly result and the threshold result.

## How an operator configures limits

Open **Integrations**, then **Alarm and threshold policies**. Select a signal
from the catalog. Configured registry signals and signals observed on the
normalized historian path are both listed. Review the suggested manifest or
imported values, select a mode, edit warning and critical boundaries, and save.
The next processed events use the saved policy version. A signal that has not
yet produced an event may still be added to `config/assets.yaml` first.

The supported modes are `outside_range`, `above`, `below`, `between_range`, and
`bad_quality`. `deadband`, `on_delay_seconds`, and `off_delay_seconds` are
available to avoid alarm chatter. The Python fallback applies these lifecycle
controls in process-local state. A production Flink deployment must implement
the same state machine as keyed state before claiming alarm lifecycle
continuity across worker restarts or rescaling.

## Discovery and caching

The asset/tag selector does not scan the complete historian for every click.
The fan-out historian sink upserts observed `(site, asset, tag)` pairs into the
metadata catalog after a successful write. Catalog reads use indexed metadata
queries and a versioned in-process cache. Registry file changes and catalog
updates change the catalog version. Existing historical rows from before the
catalog migration are not silently inferred on every UI request; use the
reconciliation/backfill operation when an already-populated historian must be
discovered.

This is intentionally not a Spark job. Dropdown discovery is a small metadata
query; Spark belongs in batch analytics or dataset construction, not in an
interactive control-plane request.

## What remains site-owned

The site operator owns engineering validation of the limits, PLC/OPC UA/DCS
configuration, credentials, alarm philosophy, acknowledgement workflow,
retention, and safety interlocks. The platform records and evaluates policy;
it does not replace a PLC safety function or automatically write control values
back to equipment.

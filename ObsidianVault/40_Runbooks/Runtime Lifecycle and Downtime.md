# Runtime Lifecycle and Downtime

The platform now distinguishes three useful runtime conditions without adding
another service:

- `running`: valid source events arrive within the expected interval.
- `recovering`: the connector is reconnecting after a transport interruption.
- `interrupted`: no valid event has arrived for three expected intervals or the
  connector reports an error.
- `planned_downtime`: the source/runtime was intentionally stopped.

Use `GET /api/v1/observability/source-health?expected_interval_seconds=10` to
inspect the classification. The expected interval must match the source's
sampling period; it is diagnostic metadata, not a command to the PLC.

Planned stops preserve historian continuity as a time gap and should be
configured by the operator. Unexpected stops use connector retry, Kafka offset
retention, Flink checkpoints, disk store-and-forward where enabled, and
idempotent historian writes to recover without fabricating data.

The platform owns classification and recovery contracts. Production calendars,
maintenance schedules, retention, checkpoint storage, and plant-specific outage
policies remain user-owned.

## Reconnection UI Decision

Automatic reconnection is runtime behavior, not a user-maintained schedule.
The platform should retry with bounded backoff and expose the recovery state.
Operators should not need to set a periodic reconnect timer for every source.

The current release intentionally has no reconnection scheduler UI. Existing
source enable/disable controls and source-health diagnostics are sufficient.
Add a maintenance-window UI later only when operators need planned outage
labels or alert suppression. Keep the actual production calendar in the
customer's MES or maintenance system.

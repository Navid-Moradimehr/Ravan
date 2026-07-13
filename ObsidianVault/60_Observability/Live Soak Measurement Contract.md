# Live Soak Measurement Contract

The live single-site and multisite tests measure admitted traffic, not merely
the requested generator rate. Each mock generator uses Kafka delivery
callbacks and writes a report to `.datastream/logs` with attempted,
acknowledged, failed, queue-full, and effective-rate values.

The report is valid only when the downstream accounting is collected as well:
Kafka offsets, consumer lag, historian row deltas, processed rows, AI output
rows, DLQ deltas, duplicates, latency percentiles, and the drain duration.
The `live_soak_accounting` module contains the deterministic rules and is
covered by unit tests.

## Current phase

- Measurement foundation implemented and committed.
- Generator scheduling no longer accumulates per-event sleep drift.
- Delivery failures and producer queue saturation are visible.
- Existing single-site and multisite scripts remain compatible wrappers.
- Full stage-level accounting and resource time-series collection remain in the
  next implementation phase.

Fan-out services now expose bounded Prometheus counters and histograms for
batch outcomes, accepted/rejected events, failed writes, and sink latency.
Metrics are labelled only by service, topic, and status.

The Windows runners use a generator duration rather than immediately killing
the child process. This is required for delivery callbacks and final JSON
reports to be flushed reliably.

## Measured optimization

The threshold-policy manifest lookup is now cached by asset-file modification
time. The 5,000-event reference pipeline increased from 132.53 to 10,690.41
events/sec, while p95 latency fell from 11.9697 ms to 0.1267 ms. See
`docs/benchmark-results-2026-07-13-threshold-cache.md` for the exact method and
limits of this result.

The Docker Flink lifecycle now cancels previously active jobs with the owned
job name before submitting a replacement. The runtime check must show one
active job and no duplicate consumers.

## Interpretation rule

Never compare historian totals to the configured rate alone. First verify the
generator acknowledged count, then account for historian rows, DLQ rows, and
remaining Kafka lag. Unexplained acknowledged events fail the run.

# Clock Quality Policy

The edge publisher always writes the original source payload to the raw Kafka
topic before validation. This preserves replay and auditability even when a
device clock is wrong. After canonical validation, the optional clock policy
checks the source timestamp against the edge host clock.

Configure the policy with:

```text
QUALITY_CLOCK_MODE=observe|warn|reject
QUALITY_MAX_CLOCK_OFFSET_SECONDS=300
```

`observe` records a Prometheus counter and accepts the normalized event.
`warn` does the same and emits a warning in the edge log. `reject` sends the
validated event inside a DLQ record and does not publish it to
`industrial.normalized` or the legacy compatibility topic. A rejected record
remains available in `industrial.raw` and can be replayed after correction.

Use `observe` while commissioning a plant, `warn` while operators fix clock
synchronization, and `reject` only after NTP/PTP or an equivalent process has
been verified.

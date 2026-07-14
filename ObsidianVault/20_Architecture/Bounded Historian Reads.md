# Bounded Historian Reads

Historian remains the hot operational store. Trend APIs now cap returned points
and use Timescale buckets for dense ranges. This protects the UI and API from
large read amplification while keeping the event write path unchanged.

```text
UI trend -> bounded historian API -> Timescale predicate/time_bucket -> chart
```

Lakehouse and BI tools remain the owners of long-range analytical scans.

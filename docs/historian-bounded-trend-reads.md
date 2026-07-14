# Bounded Historian Trend Reads

Trend reads now preserve the existing `asset_id`, `tag`, and `hours` API while
accepting optional `start`, `end`, `max_points`, and `aggregation` parameters.
The default maximum is 2,000 points. Dense ranges use TimescaleDB
`time_bucket(...)` and return bounded aggregates; `raw` remains available for a
bounded raw sample. This is an operational historian optimization, not a Spark
dependency and not a replacement for a lakehouse query engine.

The UI trend uses explicit time/value axis labels, a thinner 1.5px line, and
does not connect missing points. Grafana remains the better surface for shared,
long-range, multi-series analysis.


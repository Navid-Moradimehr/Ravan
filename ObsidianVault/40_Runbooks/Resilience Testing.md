# Resilience Testing

Run the deterministic local campaign first:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark resilience --events 10000 --outage-events 2000 --report-dir .datastream/reports/resilience
```

It can run without Docker or real PLCs. It uses the production event validator
and disk spool implementation and verifies that unique valid events are not
lost when delivery is unavailable. Then run the Docker-backed `industrial-soak`
campaign to measure live Kafka, processing, historian, Prometheus, and restart
behavior. Neither test substitutes for validation against the customer's
actual PLC drivers, network, storage, and operational procedures.

## Real-Time Multisite Soak

Use `scripts/multi-site-live-soak.ps1` for a wall-clock multi-site load test.
It starts multiple site-qualified generators in parallel and keeps them
running for the requested window while the downstream runtime, fan-out
consumers, historian, and AI gateway remain live. This is the closest local
approximation to a multi-site industrial deployment, but it still does not
certify real PLC timing or a customer's production network.

## Single-Site vs Multisite Comparison

On 2026-07-13, the same machine ran both the single-site and multisite live
soaks for 15 minutes each. The active Flink job stayed `RUNNING` in both runs
and fanout lag stayed at 0 at the final snapshot.

The final historian-write counters were:

- single-site: `industrial_events=2,226`, `processed_events=2,210`, `ai_enriched=1,754`
- multisite: `industrial_events=3,049`, `processed_events=3,036`, `ai_enriched=2,171`

The multisite run produced more data, but not linearly more. That is a useful
signal for release planning: the stack is stable on one node, but additional
sites will hit the single-node ceiling earlier than a perfect scale-out model
would suggest.

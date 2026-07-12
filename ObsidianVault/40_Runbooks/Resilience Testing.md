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

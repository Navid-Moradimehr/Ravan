# Multi-Site Simulation

Run the local multi-site campaign with:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark multi-site-simulation `
  --sites 3 `
  --events-per-site 10000 `
  --outage-events-per-site 2000 `
  --report-dir .datastream/reports/multi-site
```

Each simulated site has its own source identity, protocol mix, line and asset
namespace, and disk spool. The simulator sends events through the canonical
validator, normalization, and scoring logic. During the simulated central
outage, each site queues events locally. Recovery replays those queues into a
central idempotent event store.

The campaign checks:

- every site recovers its queued records;
- central event IDs remain unique;
- site-qualified source and asset context is retained;
- no event is stored under an unknown site;
- no cross-site contamination is introduced;
- normalization and scoring execute for every accepted event.

This is a platform-contract simulation, not proof that a customer's network,
Kafka federation, MirrorMaker configuration, or central lakehouse is correctly
deployed. A real rollout must additionally validate firewall rules, broker
replication, retention, site clocks, bandwidth, credentials, and actual PLC
driver behavior.

## Deployment Interpretation

The result supports the platform's intended architecture: independent edge
installations can collect and buffer locally while a central system consumes
site-qualified events. A company can choose a central Kafka deployment, a
federated Kafka design, or independent site installations that write to a
central lakehouse. The platform provides the event, site, mapping, lineage, and
replay contracts; the customer's network and storage topology remain owned by
the deployment team.

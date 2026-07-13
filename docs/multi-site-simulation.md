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

## Latest Local Result

On 2026-07-13, the current Docker-backed multi-site simulation passed with:

- `3` simulated sites
- `10,000` events per site
- `2,000` queued outage events per site
- `30,000` total central events written
- `0` duplicate central IDs
- `0` cross-site contamination events
- `0` site isolation errors
- `100%` replay recovery for every site

The run completed in `3.673992` seconds and reported `8,165.50` events/sec
for the local contract simulation. It did not expose any new pipeline defects.
This remains a contract-level simulation, not a certification of real plant
hardware, site networking, or customer storage topology.

## Live Soak Comparison

On 2026-07-13, a separate 15-minute wall-clock live soak was run on the same
machine with the same downstream stack.

- single-site live soak: `industrial_events=2,226`, `processed_events=2,210`, `ai_enriched=1,754`
- multisite live soak: `industrial_events=3,049`, `processed_events=3,036`, `ai_enriched=2,171`

The multisite run kept final fanout lag at 0, but it only produced about 37%
more historian writes than the single-site run. That is the clearest local
signal that the platform is stable on one node but will need additional nodes
for real multisite growth if the operator wants near-linear scaling.

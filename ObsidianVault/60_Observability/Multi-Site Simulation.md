# Multi-Site Simulation

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

The run completed in `3.673992` seconds and reported `8,165.50` events/sec.
It did not expose new pipeline defects. This is still a contract simulation,
not evidence that real site networking, PLC drivers, or customer storage are
correctly deployed.

The final local hardening phase now includes a multi-site simulator. It uses a
separate disk spool per site, site-qualified event identities, OPC UA/MQTT/
Modbus protocol labels, canonical validation, normalization, scoring, central
outage queueing, replay, and idempotent central storage.

The verification checks recovery completeness, unique central IDs, site context
preservation, normalized/scored counts, and cross-site isolation. It passed the
3-site local run with 3,000 events, 750 queued outage events, 750 replays,
3,000 unique central events, and zero isolation or cross-site errors.

This validates the logical platform contracts. It does not validate a real
Kafka federation, physical network, lakehouse, PLC driver, or customer firewall
configuration.

## Live 15-Minute Local Comparison

On 2026-07-13, a live 15-minute comparison was run on the same machine with the
same Docker-backed downstream stack:

- single-site: one live generator at 100 events/sec
- multisite: three live generators at 100 events/sec each

The final historian-write counters were:

- single-site: `industrial_events=2,226`, `processed_events=2,210`, `ai_enriched=1,754`
- multisite: `industrial_events=3,049`, `processed_events=3,036`, `ai_enriched=2,171`

Both runs held fanout lag at 0 in the final snapshot. The multisite run was
healthy, but it only increased write volume by about 37% on one node instead of
scaling linearly with three equal-rate sites. That is the clearest local signal
that the node ceiling is visible and that multi-node deployment will matter for
real multisite growth.

# Multi-Site Simulation

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

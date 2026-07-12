# Hardening Benchmark Results: 2026-07-12

## Automated Regression

- Python tests: `555 passed, 4 warnings`
- Warnings are dependency deprecations and an existing pandas interpolation
  deprecation; no test failures occurred.
- Deployment preflight: passed for the compose file, single-site profile,
  project manifest, and industrial soak scenario.

## Local Resilience Campaign

Command:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark resilience --events 10000 --outage-events 2000
```

Results:

- Accepted: `9,897`
- Rejected malformed: `103`
- Injected duplicates: `88`
- Out-of-order timestamps: `140`
- Queued during outage: `1,961`
- Replayed: `1,961`
- Unaccounted: `0`
- Pending spool after recovery: `0`
- Peak pending spool: `1,961`
- Peak memory: `4,651.56 KB`
- Elapsed: `17.696823 seconds`

This validates local event accounting and recovery contracts. It does not
measure Kafka or TimescaleDB throughput.

## Multi-Site Campaign

Command:

```powershell
py -3.13 -m services.cli.datastreamctl benchmark multi-site-simulation --sites 5 --events-per-site 5000 --outage-events-per-site 1000
```

Results:

- Sites: `5`
- Events generated: `25,000`
- Central unique events: `25,000`
- Queued per site: `1,000`
- Replayed per site: `1,000`
- Cross-site events: `0`
- Central duplicate IDs: `0`
- Site isolation errors: `0`
- Normalized events: `25,000`
- Scored events: `25,000`
- Measured local simulation rate: `15,132.13 events/sec`
- Elapsed: `1.652114 seconds`

This validates the logical multi-site contract with independent site spools and
site-qualified identities. It does not validate a real Kafka federation,
MirrorMaker deployment, network, lakehouse, PLC, or firewall configuration.

## Docker Smoke Verification

- API health: HTTP `200`
- AI gateway health: HTTP `200`
- Dashboard `/historian`: HTTP `200`
- Prometheus readiness: HTTP `200`
- Flink job `iot-anomaly-processor`: `RUNNING`

The stack was restarted before this verification. The migration and topic-init
containers exited after completing their initialization work, which is expected
for one-shot jobs.

The live `industrial-soak --smoke` command was also attempted. It exceeded the
local command timeout during Docker rebuild/reconciliation before producing a
campaign report; no service failure was observed afterward and the stack
returned to the healthy state above. The deterministic resilience and
multi-site campaigns are the completed release-gate results for this session.

# Update and Release Operations

## Implemented now

- `datastreamctl update check` reads an operator-supplied release manifest.
- `GET /api/v1/system/update-status` exposes the same read-only result.
- The dashboard can show a deduplicated in-app toast when a newer version is
  available.
- The feature is disabled by default and performs no artifact download.

## Operator settings

Set `DATASTREAM_UPDATE_CHECK_ENABLED=true` and
`DATASTREAM_UPDATE_MANIFEST_URL` to a GitHub release manifest or an internal
mirror. Keep it disabled in air-gapped deployments.

## Not implemented yet

Automatic replacement is intentionally deferred until an installer/update
agent can verify signatures, create backups, drain ingestion, apply migrations,
run health checks, and roll back. The current manual sequence is stop, backup,
replace, migrate, start, doctor, and release-gate.

Compose health checks and restart policies are platform-owned defaults. CPU,
memory, disk quotas, and log retention remain deployment-owned because an edge
PC and a plant server have materially different safe limits.

Legacy historian deduplication is disabled by default and can be enabled for a
planned maintenance run with `RUN_HISTORIAN_DEDUPE=true`.

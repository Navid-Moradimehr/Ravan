# Self-Hosted Install Guide

This guide describes the first practical install path for the open-source release.

## Goal

Install the platform so a company can run it inside its own network without giving the project cloud credentials or shared secrets.

## What ships

- `datastreamd`: runtime supervisor
- `datastreamctl`: operator CLI
- `config/`: site and project configuration
- `data/`: sample benchmarks and replay packs
- `backups/`: local backup output

## Recommended install layout

Use a single site root per deployment:

```text
/opt/datastream/<project>/<site>/
  config/
  data/
  logs/
  models/
  backups/
```

On Windows, use a matching `C:\Datastream\<project>\<site>\` layout.

## Install flow

1. Install the package.
2. Copy the project manifest and site profile into the site root.
3. Put operator-owned secrets into the local secret store or environment.
4. Start `datastreamd`.
5. Run `datastreamctl doctor`.
6. Run `datastreamctl status`.
7. Run a backup drill before connecting the site to federation or cross-site replication.

## Linux example

```bash
pip install -e .
datastreamd up --site-profile config/site-profiles/single-site.yaml
datastreamctl doctor
datastreamctl status
```

For systemd deployments:

```bash
datastreamctl project-manifest package config/project-manifest.yaml /tmp/datastream --site-id demo-site --format both --layout systemd
```

Then install the generated `systemd/install.sh` on the target host.

For Kubernetes deployments, use the Flink operator runbook at
[`docs/flink-operator-runbook.md`](docs/flink-operator-runbook.md) and the
example deployment in `k8s/flink-operator/flinkdeployment.yaml`.

## Windows example

Use the same package export flow and keep the runtime rooted under a local directory that the operator controls.

Do not require WSL2 for the production install. If a team wants WSL2 for development or demos, treat it as an optional workstation convenience, not a bundled runtime dependency.

## Upgrade flow

1. Stop the runtime.
2. Export or verify the current package.
3. Save a local backup and checksum bundle.
4. Install the new version.
5. Restart `datastreamd`.
6. Re-run `datastreamctl doctor` and the site-profile benchmark report.

## What operators own

- broker endpoints
- historian endpoints
- model endpoints
- API keys or local auth tokens
- TLS materials
- backup destinations
- network placement

## What the platform owns

- runtime orchestration
- deterministic exports
- local benchmark/report generation
- backup/restore drill helpers
- protocol normalization and bridging contracts

## Why this is enough for the first release

The project should be installable before it is fully packaged. This guide gives integrators a repeatable path while the packaging story continues to mature.

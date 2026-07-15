# Local Kubernetes Rehearsal

This guide covers the local `kind`-based rehearsal path for the platform's
Kubernetes deployment contract.

## Purpose

Use this path when you want to validate:

- generated Kubernetes bundles
- the Flink Kubernetes Operator install flow
- savepoint-oriented upgrade semantics
- single-node local operator reconciliation
- local image loading into a disposable cluster

This is a rehearsal path, not a production deployment guide. It helps you
check that the repo's Kubernetes artifacts are internally consistent before a
real cluster rollout.

## What this path does

- creates a disposable `kind` cluster
- installs the Apache Flink Kubernetes Operator if you provide a chart repo URL
- validates generated site bundles through `datastreamctl local-kubernetes-rehearsal`
- optionally applies the platform `FlinkDeployment`
- optionally loads a local Flink job image into the cluster

## What this path does not do

- it does not replace the Compose release path
- it does not validate multi-node production capacity
- it does not configure site-owned network policy, identity, or storage
- it does not install the operator for you unless you pass a chart repository URL

## Prerequisites

- `kind`
- `kubectl`
- `helm`
- Docker Desktop or a compatible Docker daemon
- the repository checked out locally

If you plan to apply the `FlinkDeployment`, also provide a reachable registry
image or load a locally built image into `kind`.

The helper prefers the repository `.venv` for Python and can also resolve
`kind` and `helm` from the Windows WinGet package cache if they were installed
in the current user profile before the shell PATH is refreshed.

## Recommended flow

1. Create or reuse a `kind` cluster.
2. Install the Flink Kubernetes Operator.
3. Run `scripts/kind-rehearsal.ps1` to validate generated bundles.
4. Optionally apply `k8s/flink-operator/flinkdeployment.yaml`.
5. Inspect the operator, JobManager, and TaskManager pods.
6. Remove the cluster when the rehearsal is complete.

## Example command

```powershell
scripts\kind-rehearsal.ps1 `
  -OperatorRepoUrl "https://downloads.apache.org/flink/flink-kubernetes-operator-<OPERATOR-VERSION>/" `
  -OperatorChartVersion "<OPERATOR-VERSION>" `
  -PlatformImage "data-stream/flink-job:latest" `
  -ApplyFlinkDeployment
```

If you only want to validate the repo-generated bundles, omit the operator repo
and deployment apply settings and let the script run the CLI rehearsal only.

## Acceptance signals

- the generated Kubernetes files are valid YAML
- the site profile export completes without missing files
- the operator install succeeds in the local cluster
- the FlinkDeployment is accepted by the operator
- the operator-owned job reaches a runnable state

## Ownership boundary

Platform-owned:

- manifests
- capacity contract
- job contract
- local rehearsal helper

User-owned:

- cluster
- operator installation details
- registry
- storage
- secrets
- network policy

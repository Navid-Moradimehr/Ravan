# Flink Operator Runbook

The platform now has a concrete Kubernetes operator path for its Flink runtime.
There is also a disposable `kind` rehearsal path in the repo for validating
generated manifests before touching a real cluster.

## Operator install

Use the Apache Flink Kubernetes Operator Helm chart in the target cluster. Keep
the install values site-owned and do not move secrets or storage into the repo.
For local validation, use `scripts/kind-rehearsal.ps1` and the companion guide
in `docs/local-kubernetes-rehearsal.md`.

## Deployment artifact

The deployment example lives at `k8s/flink-operator/flinkdeployment.yaml`.
It shows how the platform-owned Flink job maps to operator-managed lifecycle,
parallelism, and checkpoint/savepoint settings.

## What operators own

- registry image
- object storage for checkpoints and savepoints
- Kafka and cluster networking
- RBAC and service accounts

## What the platform owns

- job contract
- capacity contract
- lifecycle guidance
- operator-facing validation

## Relevant docs

- `docs/flink-operator-runbook.md`
- `docs/flink-capacity-planning.md`
- `docs/self-host-install-guide.md`

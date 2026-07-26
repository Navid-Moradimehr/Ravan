# Local Kubernetes Rehearsal

This is a disposable validation path for Ravan's Kubernetes and Flink
artifacts. It is not evidence of production multi-node capacity.

## Prerequisites

- Docker Desktop or another Docker daemon
- `kind`, `kubectl`, and `helm`
- the repository checkout

## Rehearsal

The helper validates generated bundles and can optionally apply the Flink
deployment after installing the operator:

```powershell
scripts\kind-rehearsal.ps1 `
  -OperatorRepoUrl "https://downloads.apache.org/flink/flink-kubernetes-operator-<OPERATOR-VERSION>/" `
  -OperatorChartVersion "<OPERATOR-VERSION>" `
  -PlatformImage "ravan/flink-job:latest" `
  -ApplyFlinkDeployment
```

Without the operator arguments, it only validates the generated Kubernetes
bundles. With the operator enabled, inspect reconciliation and workload state:

```powershell
kubectl get flinkdeployments -A
kubectl get pods -A
kubectl describe flinkdeployment -A
```

The rehearsal disables the operator webhook by default so it does not require
cert-manager in the disposable cluster. Use `-EnableOperatorWebhook` only
when the cluster already provides cert-manager and its issuer/trust setup.

When applying the example `FlinkDeployment`, the helper rewrites its namespace
and image to the requested rehearsal values and creates the referenced
`data-stream-flink` service account. The checked-in example remains the
deployment-owned reference manifest.

Acceptance signals are valid generated YAML, a successful site-profile export,
an accepted `FlinkDeployment`, and a runnable JobManager/TaskManager pair. The
2026-07-17 rehearsal installed the Apache Flink Kubernetes Operator, accepted
the CRD, created the requested service account, and applied the example
deployment before the disposable kind cluster was removed. It did not start a
complete industrial job because the rehearsal cluster did not include the
full Kafka/TimescaleDB/MinIO runtime dependencies. This rehearsal does not
validate production capacity, site networking, identity, storage durability,
or multi-node failure behavior.
## Multi-node rehearsal profile

Use `k8s/helm/profiles/multi-node-values.yaml` only when Kafka and
PostgreSQL/TimescaleDB are already reachable from the cluster. It enables
multiple API, AI gateway, and edge replicas, shared PostgreSQL assistant state,
Flink operator mode, HPA, and disruption budgets. The default Helm values and
Docker Compose deployment remain single-node and do not require these
dependencies.

Render it before applying it:

```powershell
helm template ravan k8s/helm -f k8s/helm/profiles/multi-node-values.yaml
```

The profile is a local control-plane rehearsal, not evidence of production
capacity. Operators still provide the image registry, broker and database
endpoints, TLS/secrets, ingress, storage classes, Flink checkpoint/savepoint
locations, and site/network policy.

For a full local traffic campaign using the same profile checks, run
`powershell -ExecutionPolicy Bypass -File scripts/multi-node-rehearsal-soak.ps1`.
It defaults to a real 900-second, three-site campaign and writes a report under
`.datastream/reports/`. Docker remains a single-node execution; only the Helm
rendering portion validates the multi-replica contract.

The July 26, 2026 rehearsal accepted 54,000/54,000 simulated Kafka events,
produced 54,000 processed historian rows, reported zero fan-out lag, and kept
the Flink anomaly job running. Kafka UI and Grafana returned HTTP 200. This is
evidence for the local path, not Kubernetes replica or real-device certification.

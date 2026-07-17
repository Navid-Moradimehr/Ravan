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

Acceptance signals are valid generated YAML, a successful site-profile export,
an accepted `FlinkDeployment`, and a runnable JobManager/TaskManager pair.
This rehearsal does not validate production capacity, site networking,
identity, storage durability, or multi-node failure behavior.

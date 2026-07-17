# Flink Kubernetes Operator Runbook

This is the Kubernetes deployment path for Ravan's Flink processing runtime.
It is optional; Docker Compose remains the simplest self-hosted deployment.

## Prerequisites

- Kubernetes, `kubectl`, and `helm`
- a site-owned image registry containing the Ravan Flink image
- Kafka access from the cluster
- checkpoint and savepoint storage, normally S3-compatible storage or MinIO
- site-owned secrets, service accounts, network policy, and TLS configuration

## Install The Operator

Use the Apache Flink Kubernetes Operator chart version approved by the site:

```powershell
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-<OPERATOR-VERSION>/
helm repo update
kubectl create namespace flink --dry-run=client -o yaml | kubectl apply -f -
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator `
  --namespace flink `
  --create-namespace
```

## Configure Ravan

Before applying `k8s/flink-operator/flinkdeployment.yaml`:

- replace the image with a site-approved registry tag
- configure Kafka connectivity
- configure checkpoint and savepoint storage
- provide cluster-specific secrets and service accounts
- set parallelism from the capacity plan
- keep `upgradeMode: savepoint` for controlled upgrades

```powershell
kubectl apply -f k8s/flink-operator/flinkdeployment.yaml
kubectl get flinkdeployments -A
kubectl get pods -A
kubectl logs -n flink deploy/flink-kubernetes-operator -f
```

The job is healthy when the operator reports reconciliation success and the
JobManager and TaskManager pods reach `Running`. Do not run the Python fallback
processor for the same topic while this operator-owned job is active.

Platform-owned: the Flink job contract, event topics, runtime image contract,
and capacity guidance. User-owned: the cluster, registry, Kafka endpoints,
storage, secrets, RBAC, network policy, and retention policy.

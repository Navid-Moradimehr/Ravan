# Flink Operator Runbook

This runbook covers the Kubernetes path for the platform's Flink processing
runtime.

## Scope

- install the Apache Flink Kubernetes Operator
- apply the platform Flink deployment example
- validate the operator-managed job
- keep checkpoint and savepoint storage operator-owned

This is a deployment-owned path. It does not replace the Docker Compose path.

## Prerequisites

- a Kubernetes cluster
- `kubectl`
- `helm`
- a container registry that can host the platform Flink image
- checkpoint and savepoint storage, typically S3 or MinIO-compatible object
  storage
- Kafka broker access

## 1. Install the operator

Use the official operator Helm chart. Apache Flink documents both the bundled
chart path and the repository path. A repository install looks like this:

```powershell
helm repo add flink-operator-repo https://downloads.apache.org/flink/flink-kubernetes-operator-<OPERATOR-VERSION>/
helm repo update
kubectl create namespace flink
helm install flink-kubernetes-operator flink-operator-repo/flink-kubernetes-operator `
  --namespace flink `
  --create-namespace
```

If your cluster uses a site-approved values file, pass it with `-f` and keep the
operator defaults under review before production rollout.

## 2. Prepare the platform deployment

The concrete deployment template lives at
`k8s/flink-operator/flinkdeployment.yaml`.

Before applying it:

- replace `spec.image` with the image pushed to your registry
- point checkpoint and savepoint storage at your site-owned object store
- set any network policies, service accounts, and secrets required by your
  cluster
- keep operator autoscaling settings in the operator Helm values, not inside
  the workload spec

## 3. Apply the Flink deployment

```powershell
kubectl apply -f k8s/flink-operator/flinkdeployment.yaml
```

## 4. Validate the deployment

```powershell
kubectl get flinkdeployments -n data-stream
kubectl describe flinkdeployment data-stream-flink-job -n data-stream
kubectl get pods -n data-stream
kubectl logs -n flink deploy/flink-kubernetes-operator -f
```

What to look for:

- the operator reports the deployment as reconciled
- JobManager and TaskManager pods appear in the target namespace
- the job reaches a running state
- the configured parallelism matches the capacity plan

## 5. Change management

For controlled upgrades:

1. update the image tag or job artifact in `flinkdeployment.yaml`
2. keep `upgradeMode: savepoint`
3. re-apply the manifest
4. confirm the operator completes the savepoint-based reconciliation

For controlled shutdowns:

1. suspend or delete the deployment through Kubernetes
2. verify checkpoint/savepoint storage still contains the latest state
3. redeploy from the same manifest when ready

## 6. How this relates to the repo

- `docs/flink-capacity-planning.md` explains how to size the job
- `k8s/helm/values.yaml` stores the platform capacity contract
- `k8s/flink-operator/flinkdeployment.yaml` shows how that contract maps to a
  real operator-managed resource

## Ownership boundary

Platform-owned:

- job contract
- capacity contract
- runtime lifecycle guidance
- default parallelism and rescaling guidance

User-owned:

- registry image
- object storage
- Kafka brokers
- network policy
- secrets
- cluster-specific RBAC

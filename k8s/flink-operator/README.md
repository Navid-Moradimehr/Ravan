# Flink Operator Example

This directory contains a concrete Apache Flink Kubernetes Operator example for
the platform's Flink-first deployment path.

## What this is

- a `FlinkDeployment` example for the platform-owned processing job
- a reference for operators who want stateful rescaling and savepoint-backed
  upgrades
- a deployment-owned artifact, not a new platform service

## What this is not

- it is not an installer for the operator itself
- it is not a replacement for the Helm chart values in `k8s/helm/values.yaml`
- it is not a custom autoscaler

## Operator-owned prerequisites

Before applying the example, install the Flink Kubernetes Operator in the
target cluster and provide the following:

- a container registry image for the Flink job
- checkpoint and savepoint storage, usually S3 or MinIO-compatible storage
- Kafka broker access
- any deployment-owned secrets or network policies
- operator autoscaling settings in the operator Helm values, not in the
  deployment manifest itself

## Example workflow

1. Install the Flink Kubernetes Operator in the namespace or cluster.
2. Build and publish the Flink job image from `docker/Dockerfile.flink-job`.
3. Update the `image` field in `flinkdeployment.yaml` to point at the published
   registry image.
4. Apply the manifest with `kubectl apply -f`.
5. Watch the operator-managed job and compare the chosen parallelism with the
   capacity plan reported by `datastreamctl flink capacity-plan`.

## How the example relates to the chart

The Helm chart already carries the capacity contract in values and configmap
data. This manifest shows how those values translate into a real operator-owned
deployment resource.

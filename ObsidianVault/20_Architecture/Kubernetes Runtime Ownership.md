# Kubernetes Runtime Ownership

The Helm chart has one explicit owner for the Flink runtime. With
`flinkJob.operator.enabled=true`, it renders a `FlinkDeployment` using the
PyFlink `PythonDriver` contract and does not render the legacy Flink
Deployment/HPA. With the flag disabled, the local fallback Deployment can be
used. Both must not be enabled for the same release.

The chart injects `KAFKA_BROKERS`, matching the runtime services. Service
commands and image overrides are explicit for API, AI gateway, processor,
edge ingest, and local Flink fallback so deployment cannot depend on an
accidental image entrypoint.

This is a deployment contract and local rehearsal improvement. It does not
claim a production Kubernetes cluster, operator installation, object-store,
network-policy, or site-owned secret configuration.

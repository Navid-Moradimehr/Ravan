# Flink Capacity Planning

The platform uses Flink as the production processing runtime. Python remains
an explicit fallback for lightweight local deployments. A deployment must not
run both consumers against `iot.raw` during normal operation.

## Compose

Compose performs bounded startup sizing. It does not continuously resize a
stateful Flink job. Plan capacity with:

```powershell
py -3.13 -m services.cli.datastreamctl flink capacity-plan `
  --topic industrial.normalized `
  --partitions 18 `
  --host-cpu 24 `
  --host-memory-mb 32768 `
  --max-parallelism 18
```

The planner limits parallelism by Kafka partitions, host CPU, host memory, and
configured bounds. For the resulting TaskManager count, set
`FLINK_TASKMANAGER_SLOTS` and use `docker compose --scale taskmanager=N`.

## Kubernetes

The Helm chart defaults Flink autoscaling to `operator` mode. The generic HPA
for the Flink deployment is only rendered when `flinkJob.autoscaling.mode=hpa`
is explicitly selected. CPU-only HPA is not the recommended stateful scaling
path.

For Kubernetes production deployments, install the Apache Flink Kubernetes
Operator and map the Helm capacity values into its `FlinkDeployment` or
`FlinkSessionJob` resource. The operator should control savepoints, stateful
rescaling, job lifecycle, and its lag/busy-time autoscaler. The platform chart
keeps these values in the site configuration but does not install the cluster-
scoped operator CRD automatically.

Recommended controls are:

- `maxParallelism` with useful divisors for future rescaling;
- target utilization around `0.70`;
- a 15-minute metrics window;
- a 5-minute stabilization interval;
- a bounded catch-up duration;
- checkpoint and savepoint storage owned by the deployment operator.

The source parallelism cannot exceed the Kafka partition count. Keyed operator
parallelism may be bounded differently, but stateful changes must preserve
checkpoint/savepoint compatibility.

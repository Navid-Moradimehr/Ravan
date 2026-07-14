# Source Onboarding Runtime

The source registry is a lightweight control-plane artifact. It is not a secret
store and it is not proof that a protocol is connected.

```text
API/UI metadata -> /data/connection-registry.json -> edge supervisor
                                                     -> protocol connector
                                                     -> industrial.raw
                                                     -> normalization/Kafka
```

The Docker API and edge containers now use the same mounted registry path. The
edge supervisor reconciles connection versions and enabled state in-process. This
keeps one-server Compose deployments simple while leaving a clear future boundary
for a distributed edge manager.

[[Industrial Edge Pipeline]]
[[AI Reporting Policy and Jobs]]

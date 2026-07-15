# Model Data Collection Contracts

The platform's first world-model hardening phase preserves evidence without
becoming a model-training runtime.

- Scalar telemetry remains canonical and replayable.
- Rich observations use checksummed S3/MinIO or approved file references.
- Schema-v2 telemetry records clock, sequence, calibration, topology and
  context evidence while schema-v1 remains compatible.
- Standard action, outcome and episode-boundary payloads are optionally
  validated; custom operational events remain extensible.
- The platform does not infer rewards, train models or execute PLC actions.

Next dependency: the lakehouse must archive operational events and artifact
references in dedicated tables before trajectory compilation can be trusted.

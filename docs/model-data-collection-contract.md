# Model-Data Collection Contract

The platform collects evidence for future representation learning and
model-based control. It does not train JEPA, Dreamer, MuZero, or any other
model and it never invents rewards or sends actions to a PLC.

Scalar telemetry remains on the canonical industrial-event path. Large
observations such as images, video, audio, waveforms and tensors are stored in
operator-owned MinIO or S3-compatible storage; Kafka carries a checksummed
`industrial.observation-artifacts` reference. This keeps the streaming path
bounded while preserving the data needed by multimodal training.

Schema-v2 telemetry may include sequence number, clock identity and sync
status, timestamp uncertainty, calibration version, topology version and
operating-context identity. Schema-v1 events remain valid.

Operational events remain extensible. When `schema_ref` is declared, the
platform validates standard action, outcome and episode-boundary payloads.
Custom company payloads remain supported. Users still define the meaning of a
reward, safety constraint, action vocabulary and episode boundary.

The artifact reference contract is metadata only. Credentials, binary payloads
and retention policies remain deployment-owned. Allowed object references are
explicitly `s3://` or deployment-approved `file://` locations.

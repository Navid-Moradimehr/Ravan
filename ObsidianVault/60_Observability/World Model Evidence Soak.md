# World Model Evidence Soak

The dedicated runner is `scripts/world-model-soak.py`.

It runs three simulated sites for 15 minutes, sends three scalar channels per
site, publishes actions, outcomes, and episode boundaries, uploads real small
artifact bytes to MinIO, and publishes immutable artifact references to Kafka.
It then compiles the captured records with manifest v2.

The result is `.datastream/reports/world-model-soak/world-model-soak.json`.
The acceptance result requires zero Kafka delivery failures, successful
artifact upload, a valid compiled bundle, and a complete wall-clock sample
campaign. This is local evidence validation, not real PLC or plant
certification.

## Evidence status

The last completed campaign produced 900 samples, 8,100 observations, 540
actions, 540 outcomes, and 90 artifacts. Kafka acknowledged 9,276 of 9,276
messages, Flink was `RUNNING`, TimescaleDB contained all 8,100 current
observation event IDs, and the manifest-v2 bundle passed its evidence gate.

The campaign also found a real upgrade defect: a pre-existing telemetry-shaped
`industrial.operational_events` table could silently lose operational envelope
fields. The sink now rejects cross-family schemas and Compose uses
`operational_events_v2`. The first rerun after that fix was interrupted because
Docker Desktop's Linux engine returned API 500 and Kafka timed out. The
corrected lakehouse persistence path therefore remains pending a healthy
Docker rerun; this note deliberately does not call that interrupted run a
pass.

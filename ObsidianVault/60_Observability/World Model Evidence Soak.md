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

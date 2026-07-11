# World Model Data Foundation

The platform is a data foundation, not a world-model training runtime. Core
capabilities are replayable telemetry, historian storage, optional Iceberg
over MinIO/S3, semantic context, operational-event transport, provenance, and
portable training bundles.

Users own plant-specific adapters, rewards, action semantics, episode
boundaries, safety constraints, retention, IAM, and model training. JEPA can
start from passive observations; Dreamer and MuZero require explicit actions,
outcomes, and episode context.

# Data Provenance Guide

Every canonical event may carry the configuration identity needed to reproduce
its interpretation:

- `source_connection_id`
- `source_config_version`
- `mapping_version`
- `schema_version`
- `lineage_id`

Registry-managed edge sources populate these values when they map a payload.
Legacy environment sources receive stable `legacy-<protocol>:v1` identities.
The values travel with normalized and processed events and are retained by
new lakehouse tables. Existing tables remain readable through compatibility
projection and need an explicit migration before new columns can be queried.

The event-level fields are intentionally cheap metadata, not a second high-
volume lineage database. Dataset manifests and dataset-build records provide
the higher-level lineage: source topics/tables, time range, selected tags,
semantic topology version, processing version, and output artifacts.

When a source mapping changes, update the connection registry rather than
editing an old record. The registry increments `config_version`; a new
training dataset must declare which version it includes. This prevents a
model-training run from silently combining old and new tag meanings.

For a production rollout, users should also record their own calibration,
PLC-program, MES-schema, and topology identifiers in the connection or
semantic metadata. The platform cannot infer those identities from a network
address.

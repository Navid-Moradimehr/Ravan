# Data Provenance

Canonical events carry source connection, source configuration, mapping,
schema, and lineage identities. Registry-backed edge sources populate these
fields before validation and publication, so a normalized training record can
be traced back to the interpretation applied at ingestion.

The fields are lightweight event metadata. Higher-level lineage remains a
metadata-plane concern and should identify dataset builds, semantic topology,
processor versions, model versions, and output artifacts.

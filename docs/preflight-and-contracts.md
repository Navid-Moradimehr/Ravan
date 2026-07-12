# Preflight And Event Contracts

Run the deployment preflight before starting a local or site deployment:

```powershell
py -3.13 -m services.cli.datastreamctl preflight
```

The command validates the compose file, site profile, project manifest,
cross-site manifest references, and industrial soak scenario. It composes the
existing validators; it does not replace deployment-specific secret, network,
PLC, or storage checks owned by the installing company.

The event contract tests verify that an event keeps its identity and context
through canonical validation, normalization, and runtime enrichment. The
checked fields include event ID, source, asset, tag, site, timestamp, unit,
mapping version, source configuration version, and lineage ID.

The runtime path is still intentionally event-driven: validation occurs at the
edge boundary, normalized data is published to Kafka, processors enrich it,
and sinks persist it. Preflight and contract tests only make failures visible
earlier; they do not introduce a second pipeline.

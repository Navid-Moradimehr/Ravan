# Operational Event Contract

`industrial.operational` is a domain-neutral event channel for actions,
outcomes, context changes, maintenance, annotations, and episode boundaries.
It complements `industrial.normalized`, which remains the primary telemetry
contract.

The platform owns the envelope, schema version, Kafka delivery, replayability,
and optional lakehouse archive. Users own the payload semantics and adapters
for PLC audit logs, MES, ERP, CMMS, SCADA, operator systems, and quality data.

Operational events are not written directly by the API to the historian. They
are published first to Kafka and can be archived by the optional operational
fan-out consumer. This preserves the same recovery boundary as telemetry.

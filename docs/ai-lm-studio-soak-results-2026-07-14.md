# AI and LM Studio Soak Results

## Environment

- LM Studio endpoint: `http://192.168.100.7:1234/v1`
- Model: `openai/gpt-oss-20b`
- Kafka input: `iot.processed`
- AI output: `iot.ai_enriched`
- Policy: anomaly enabled, warning severity, 20-second duration, three samples
  minimum, replay excluded

## Results

The definitive five-minute stream sent 900 events from three source identities
and completed without producer errors. The sources represented OPC UA, MQTT,
and Modbus input paths. The simulator includes the boundary sample at elapsed
second 20, so a configured 20-second warning interval is testable rather than
being shortened to 19 seconds.

The run created a completed sustained-anomaly report job. The latest
`iot.ai_enriched` Kafka record contained 22 warning evidence events for
`plant-a/Pump-01/Vibration`, `report_type=anomaly`,
`trigger_reason=sustained_anomaly`, `model_id=openai/gpt-oss-20b`, and
`used_fallback=false`. The AI-enriched historian row was persisted in
`ai_enriched`.

A controlled 40-second run with a 30-second warning condition then produced one
completed anomaly job. The output contained 22 warning evidence events for
`plant-a/Pump-01/Vibration`, `report_type=anomaly`,
`trigger_reason=sustained_anomaly`, and a report ID. The LM Studio response was
accepted with `used_fallback=false` and measured gateway latency of 19.93 seconds.

The earlier 35-second run with the default eight-second gateway timeout correctly
used deterministic fallback after a `ReadTimeout`. A direct small LM Studio
request completed in approximately 3.03 seconds, so the larger industrial prompt
is the relevant latency measurement.

## Operational implication

The current gateway processes one report synchronously. During the approximately
20-second model request it can temporarily stop consuming new AI input, although
Kafka retains the events and reports consumer lag. For production deployments,
the next high-value improvement is separating Kafka consumption/job claiming from
model execution with a bounded worker queue and explicit max in-flight reports.

The report is visible in Kafka UI under `iot.ai_enriched`, in the durable
`ai_report_jobs` table/API, and through the AI Reporting page. AI fan-out can
persist the summary into the historian `ai_enriched` table. Gateway metrics
expose the request latency and enrichment counters while the gateway process is
running; after a restart, the database and Kafka records remain the durable
verification sources.

The first controlled run with the default eight-second timeout used the
deterministic fallback after a model timeout. With the LM Studio deployment
timeout raised to 60 seconds, the accepted model response measured 19.93
seconds and did not use fallback. The policy was restored after the soak, so
the test did not leave anomaly-triggered reporting enabled by default.

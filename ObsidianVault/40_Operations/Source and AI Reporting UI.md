# Source and AI Reporting UI

The navigation now separates operational source management from the broader
Integrations catalog. **Sources** is for registering, testing, previewing, and
enabling connection definitions. **AI reporting** is for policy and durable job
visibility.

```text
Sources UI -> connection registry -> edge supervisor -> Kafka -> historian
AI policy UI -> metadata policy -> AI gateway -> iot.ai_enriched -> historian
```

The pages do not own credentials or authorization. They are compatible with a
deployment that starts without AuthN/AuthZ and preserve forwarded authorization
headers for installations that add their own boundary.

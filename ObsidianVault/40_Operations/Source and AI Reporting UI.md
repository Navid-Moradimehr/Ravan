# Source and AI Reporting UI

The navigation keeps one operational source-management surface inside
**Integrations**. The former `/sources` URL redirects to
`/integrations#source-connections` so bookmarks remain compatible. **AI
reporting** is for policy and durable job visibility.

```text
Integrations source editor -> connection registry -> edge supervisor -> Kafka -> historian
AI policy UI -> metadata policy -> AI gateway -> iot.ai_enriched -> historian
```

The pages do not own credentials or authorization. They work in an installation
without AuthN/AuthZ. The API built-in JWT boundary is opt-in with
`DATASTREAM_AUTH_REQUIRED=true`; browser authorization headers are still
forwarded when an operator adds an external or built-in auth boundary.

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

Source connections can be edited and structurally validated in Integrations.
The editor uses five steps: Identity, Connectivity, Discover/sample, Map data,
and Review/enable. Native protocol fields and REST JSON-path mapping are
provided without requiring backend code changes; secret values remain outside
the platform behind credential references. Test is the bounded connectivity
diagnostic and Preview displays discovered metadata without publishing data.

The AI Reporting Site ID selector represents deployment scope, not an asset or
tag. It combines IDs from the source registry and asset/tag catalog, with `*`
for the shared policy.

The recommended Command Center source card is a health summary and a link to
Integrations, not a second editor. This preserves one source of truth and works
before and after user-owned AuthN/AuthZ is added.

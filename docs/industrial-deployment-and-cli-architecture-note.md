# Industrial Deployment And CLI Architecture Note

This note turns the recent review into a stable operating model for the platform.

## Executive conclusion

The current platform architecture is already aligned with common industrial deployment patterns.

It does **not** need a major redesign to support:

- OPC UA and other protocol sources
- site-local collection and processing
- historian-backed storage
- central aggregation or lakehouse export
- manual dashboard composition
- CLI-based installation and operations

What it needs is mostly clarity and explicit operating guidance, not a new architecture.

## 1. OPC UA raw vs processed data

In real industrial systems, OPC UA data is usually handled as:

- source values
- derived or calculated values
- scaled or normalized values
- quality-bearing readings
- summary or aggregated values

Industrial products generally do not create a separate pipeline just because a value came from OPC UA. They preserve source identity and quality, then allow downstream layers to interpret the value as raw, derived, or summarized.

The right rule for this platform is:

- keep the original source identity
- preserve timestamps and quality
- allow derived values to flow through the same canonical event model
- distinguish raw and processed values through metadata and naming, not through separate incompatible pipelines

That is already consistent with the current connector and historian design.

## 2. Site-local vs central deployment

The dominant industrial pattern is hybrid:

- edge or site-local runtime near PLCs and sensors
- local validation, normalization, buffering, and historian writes
- optional forwarding to central object storage, lakehouse storage, or enterprise analytics

This is the safest model for:

- low latency
- plant autonomy
- air-gapped or limited-connectivity sites
- data sovereignty
- easier OT troubleshooting

The platform should therefore be treated as a site-local system first, with a central aggregation path as an optional second layer.

That means:

- each plant or site can run its own instance
- a central platform can later consume curated exports or replicated streams
- central MinIO, S3, or lakehouse storage should be a downstream target, not a dependency for live plant operation

## 3. Dataset storage

Industrial datasets usually live in more than one place:

- historian for operational queries and replay
- object storage or lakehouse for long-term analysis and training
- curated dataset packs for benchmarks and model work

The platform should keep this split explicit:

- historian answers “what happened?”
- dataset storage answers “what should we analyze or train on?”

That split is already consistent with the current platform direction.

## 4. Dashboard behavior

Industrial dashboards are usually user-configured, not auto-generated from the number of connected devices.

Typical behavior in mature tools is:

- user selects assets, tags, alarms, or metrics
- user arranges pages, widgets, and trends
- the platform may suggest default views, but it does not force them

The correct model for this platform is the same:

- auto-discover devices and tags
- expose them in inventory and metadata
- let operators build or choose dashboard layouts
- do not automatically create one chart per sensor unless the user asks for it

That preserves flexibility and avoids a brittle UI.

## 5. CLI role

The CLI is a core operational surface, not an accessory.

It should support:

- install and uninstall flows
- health checks and diagnostics
- site profile validation
- dataset and scenario management
- benchmark runs
- backup and restore helpers
- runtime supervision
- air-gapped or headless operations

Why it matters:

- many industrial sites prefer scripted operations
- some sites have no browser access on the runtime host
- repeatability matters more than GUI convenience
- CLI commands are easier to automate in installers and CI

This is why `datastreamctl` and `datastreamd` are good architectural choices.

## 6. Platform assessment

The platform is already handling these areas well:

- connector separation
- canonical event modeling
- site-local ingestion
- historian-backed persistence
- user-configured dashboards
- CLI-based operations

The main gap is not architecture correctness. The main gap is documentation clarity and deployment guidance.

### Small improvements still worth keeping

- make site-local versus central deployment guidance even more explicit
- document raw vs derived vs summarized data as part of the event model
- document dashboard composition as user-driven, not automatic
- document the CLI as a first-class operator tool

Those are clarity improvements, not redesign work.

## 7. Final recommendation

Do not change the core architecture just to chase theoretical purity.

Keep:

- site-local runtime
- Kafka backbone
- historian
- canonical event model
- semantic correlation
- CLI operations
- optional central storage/export

That is already the right shape for an industrial open-source release.


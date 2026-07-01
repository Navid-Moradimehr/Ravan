# Multi-Site Industrial Rollout Plan

## Goal

Move Local Stream Engine from a single-site development platform to a repeatable industrial platform that can be deployed across many plants, lines, or business units without coupling one site to another.

The main design rule is simple:

- keep runtime services site-local by default
- centralize only the data that is intentionally shared
- treat cross-site aggregation as a separate control-plane concern

## What The Platform Should Own

The platform should own:

- ingestion and normalization
- stream processing
- historian storage
- AI enrichment
- local dashboards and operator tooling
- backup and restore
- site-local observability

The platform should not force users to outsource:

- model hosting
- broker placement
- historian placement
- network segmentation
- identity provider choice
- plant-specific retention policy

## Recommended Deployment Topologies

### 1. Single Site

Use for a pilot line or first plant.

- one Redpanda cluster
- one historian
- one AI gateway
- one API/UI layer
- one local backup target

This is the best starting point because it is simple to support and easy to validate.

### 2. Site-Local Fleet

Use when each plant should operate independently.

- each site gets its own broker, historian, AI gateway, and operator UI
- each site publishes its own config bundle
- each site keeps its own backup and restore schedule
- each site can run the same container/image version

This is the safest default for regulated, air-gapped, or latency-sensitive plants.

### 3. Federated Multi-Site

Use when the company needs company-wide visibility.

- each site runs a local platform stack
- a central layer receives only approved rollups, KPIs, or replicated subsets
- raw plant data stays local unless explicitly allowed
- site failure does not take the central layer down

This is the right shape for large industrial groups with multiple business units.

## Production Hardening Phases

### Phase 1: Site Profile Standardization

Lock down the configuration that must be identical across sites:

- container image tag
- service ports
- topic names
- schema versioning rules
- backup directory layout
- model backend contract

Add site-specific configuration for:

- `site_id`
- plant name
- region
- network zone
- model endpoint
- historian target
- backup target

Success criteria:

- the same release artifact starts cleanly in at least two independent site profiles
- no site profile requires code changes

### Phase 2: Runtime Isolation

Make sure one site cannot accidentally depend on another.

Required controls:

- site-local broker by default
- site-local historian by default
- site-local AI gateway by default
- site-specific config bundles
- local backups and restore paths

Operational rule:

- if the WAN goes down, the plant still runs

Success criteria:

- local ingest, processing, historian writes, and AI fallback continue during network isolation
- site startup does not require a central service

### Phase 3: Backup and Recovery

The repo already has historian backup and restore support, so the hardening work should formalize it into a site lifecycle.

Required operations:

- scheduled historian backups
- restore drills
- config bundle backups
- replay pack backups
- verified backup retention

Recommended policy:

- daily backup for the historian
- weekly restore test in staging
- one retained backup per release candidate

Success criteria:

- a site can be restored from backup without manual schema surgery
- restore time is measured and documented

### Phase 4: Observability and SLOs

Every site should publish the same baseline operational signals:

- ingest rate
- processing lag
- AI latency
- historian write latency
- backup status
- DLQ count
- broker health
- UI/API health

### Source Isolation

Inside one site, the platform should keep each PLC, gateway, and sensor network separate at the transport and storage boundaries.

Use these fields to identify a stream:

- `site`
- `line`
- `source_protocol`
- `source_id`
- `asset_id`
- `tag`

Recommended behavior:

- use the full stream identity for Kafka/Redpanda partition keys
- store the raw historian rows with source-aware metadata intact
- keep each PLC or gateway stream separate even when two sources report the same asset and tag
- bridge streams only through explicit correlation, federation, or outbound bridge rules
- aggregate up through the asset hierarchy only after storage, never by collapsing the source identity at ingest

This keeps the platform safe for a full production line with multiple PLCs and sensors feeding the same asset model.

Suggested SLOs for initial rollout:

- ingest path availability: 99.5% per site
- AI fallback availability: 100% when the model server is down
- historian backup success: 99% of scheduled jobs
- operator visibility: health checks must stay green or degrade clearly

Success criteria:

- a plant operator can tell if the issue is local, site-wide, or central
- dashboards separate service health from data-path health

### Phase 5: Cross-Site Aggregation

Do not start here. Do it only after the site-local stack is stable.

Use this layer for:

- executive rollups
- fleet-wide KPI comparison
- central audit reporting
- model performance comparison across sites

Do not use this layer for:

- active plant control
- raw ingest dependency
- mandatory approval paths for local operations

Success criteria:

- a central aggregator can fail without interrupting a site
- aggregation only consumes approved summaries or replicated subsets

### Phase 6: Release Gates

Before a production pilot, require:

- clean install on Windows and Linux
- documented site configuration bundle
- documented backup/restore procedure
- site-local rollback plan
- benchmark results on realistic mock data
- soak tests for ingest, processing, historian, and AI fallback
- clear owner boundaries for model hosting and secrets

## What The Platform Should Handle Versus What Users Should Handle

### Platform responsibilities

- request routing to the configured AI backend
- deterministic fallback summaries
- site-local configuration loading
- backup/restore workflow for historian state
- runtime health checks and diagnostics
- topic and service wiring

### User responsibilities

- provide model endpoints and credentials
- choose where brokers and historians run
- manage plant network topology
- define site naming and retention policy
- decide whether cross-site replication is allowed
- size the hardware for throughput and storage

## Rollout Sequence For A Company

1. Pilot one line in one plant.
2. Validate ingest, historian, AI fallback, and backup restore.
3. Expand to the full plant.
4. Clone the same site profile into a second plant.
5. Introduce central rollup only after the first two sites are stable.
6. Publish an internal support runbook for install, upgrade, backup, and restore.

## Operational Risks To Control

- a central model server becoming a dependency for plant ingest
- a shared historian turning into a single failure domain
- config drift between plants
- backups that exist but were never tested
- one site’s topic names or credentials leaking into another site

## Current Readiness

The repo is already close to the required shape for a site-local rollout because it has:

- site-aware event normalization
- backup and restore APIs for the historian
- a provider-neutral AI gateway
- CLI and runtime supervisor entry points
- Helm values that separate public config from secrets

Implemented in the repo now:

- a formal site profile schema with example `single-site`, `plant-local`, and `federated` YAMLs
- `datastreamctl` commands for profile validation, backup drills, and release-gate checks
- `datastreamd --site-profile` so runtime services can start from a site contract
- Helm profile overlays for `single-site`, `plant-local`, and `federated`
- a live soak harness at `scripts/site-profile-soak.ps1`

Validated locally:

- `single-site.yaml` release gate passed
- `plant-local.yaml` release gate passed
- `federated.yaml` release gate passed
- backup and restore drills passed in all three profiles
- processor restart recovery passed in all three profiles
- site-profile soak ran end to end for all three profiles

What still needs to be finished for a true multi-site production rollout:

- documented backup cadence and restore drill ownership per site
- installable packages for Windows and Linux
- site-by-site benchmark reports
- central aggregation design, if the company wants fleet-wide reporting

## Recommended Next Step

Implement a site profile contract and an operator-facing release checklist, then run the same benchmark and soak suite against at least two different site profiles.

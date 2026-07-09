# App Functionality

## What this app is

Local Stream Engine is an industrial data platform for testing streaming, analytics, historian storage, alerting, and AI-assisted operations without needing a real plant.

In plain language, it acts like a small digital factory lab:

- data comes in from simulated or real protocol connectors
- the platform normalizes that data into one common format
- analytics score the signals and detect faults
- alerts, historian views, SQL queries, dashboards, and AI summaries sit on top

## End-to-End Flow

1. A device, simulator, replay job, or external system sends telemetry.
2. The edge layer converts it into a canonical industrial event.
3. The streaming layer publishes the event to Kafka-compatible topics.
4. Analytics enrich the event with severity, anomaly signals, and fault context.
5. The historian stores the event for trend analysis and replay.
6. The UI, WebSocket streams, REST APIs, and outbound webhooks expose the result.

## Main Parts

### 1) Edge Ingestion

This is the front door of the platform.

**What it does**

- accepts industrial data from OPC UA, MQTT, Modbus TCP, and Modbus RTU
- supports local simulators and real connector configurations
- validates payloads and routes bad records to a dead-letter queue
- publishes standardized events for downstream processing

**Main inputs**

- protocol messages from simulators or real endpoints
- replayed datasets from CSV and predictive-maintenance datasets
- external events posted to the REST ingest API

**Main outputs**

- `industrial.raw`
- `industrial.normalized`
- `industrial.dlq`
- compatibility events for downstream processing

**How it performs**

- built for continuous streaming rather than batch uploads
- isolates malformed records instead of stopping the pipeline
- keeps protocol-specific complexity out of later services

**How users interact with it**

- operators start simulators and soak scripts
- engineers configure assets, tags, limits, and connector settings
- external systems can push events through the API

### 2) Canonical Event Model

This is the common language used by the platform.

**What it does**

- converts very different source protocols into one shared event shape
- adds common metadata such as asset, tag, unit, timestamps, and schema version
- makes downstream analytics and storage independent from source protocol details

**Main inputs**

- raw OPC UA, MQTT, Modbus, replay, and API events

**Main outputs**

- normalized industrial event envelopes with fields such as:
  - `event_id`
  - `source_protocol`
  - `asset_id`
  - `tag`
  - `value`
  - `quality`
  - `unit`
  - `site`
  - `line`
  - `ts_source`
  - `ts_ingest`
  - `schema_version`

**How it performs**

- reduces integration complexity across the full stack
- supports schema evolution and validation
- gives the historian, analytics, and UI a stable contract

### 3) Scenario Engine

This controls how test data behaves.

**What it does**

- applies reusable behavior patterns to incoming or replayed data
- simulates healthy and faulty operating conditions
- labels data so analytics can be evaluated against known truth

**Available scenarios**

- `normal`
- `drift`
- `spike`
- `stuck_sensor`
- `dropout`
- `noisy_sensor`
- `slow_degradation`
- `maintenance_reset`

**Main inputs**

- selected dataset
- selected scenario
- env vars or CLI flags

**Main outputs**

- modified event values and signal behavior
- labels such as:
  - `fault_type`
  - `scenario_id`
  - `ground_truth_severity`

**How it performs**

- makes testing repeatable
- helps compare expected faults with detected faults
- avoids needing expensive real-world fault collection up front

**How users interact with it**

- users choose dataset and scenario from the UI
- developers can control it via env vars or command-line flags

### 4) Stream Processing and Analytics

This is the decision-making layer.

**What it does**

- runs streaming analytics on incoming industrial data
- calculates severity and anomaly indicators
- compares detected behavior with known fault labels
- supports rule-based logic and trainable anomaly models

**Main inputs**

- normalized industrial events
- rule configuration
- asset metadata and thresholds
- scenario labels and historian context

**Main outputs**

- processed events
- alarm candidates
- anomaly scores
- fault metrics
- evaluation metrics such as precision, recall, and F1

**Current analytics methods**

- configurable rules
- rolling z-score
- EWMA
- rate of change
- stuck-value detection
- known fault vs detected fault evaluation
- optional PyOD models such as Isolation Forest, LOF, and One-Class SVM

**How it performs**

- good for online fault detection and demo-scale predictive workflows
- explainable because rules and thresholds remain visible
- extensible because model-based detectors can be added without changing the whole pipeline

**How users interact with it**

- operators see results in alarms, trends, and summary panels
- engineers tune rules, thresholds, and features
- data teams can compare ground truth against detections

### 5) AI Gateway

This turns machine events into human-readable operational context.

**What it does**

- batches processed events
- sends them to a provider-neutral LLM backend
- generates operational summaries or explanations
- falls back to deterministic summaries if the LLM is unavailable

**Main inputs**

- processed streaming events
- LLM configuration such as provider, endpoint URL, model, and batch settings

**Main outputs**

- `iot.ai_enriched`
- versioned AI summary events with source IDs, prompt version, model version, and batch metadata
- natural-language summaries
- latency and batch metrics

**How it performs**

- keeps the pipeline running even when AI is down
- adds operator-friendly context instead of only raw metrics
- works with local or remote OpenAI-compatible endpoints and local open-weight model servers
- publishes AI summaries back into Kafka so downstream consumers can replay, archive, or benchmark the AI layer independently of the UI

**How users interact with it**

- operators read summaries in the UI
- admins configure model endpoints and keys
- developers can point it to LM Studio, Ollama, vLLM, TGI, llama.cpp, Triton, or cloud APIs
- future prediction and recommendation outputs can follow the same event contract

### 6) Historian

This is the memory of the platform.

**What it does**

- stores normalized, processed, and AI-enriched streams
- supports time-based trend analysis
- powers alarm history, raw event history, SQL access, and replay
- supports TimescaleDB and ClickHouse-style historian backends

**Main inputs**

- `industrial.normalized`
- `iot.processed`
- `iot.ai_enriched`

**Main outputs**

- historical trend data
- alarm and raw-event tables
- query results
- replayable time windows

**How it performs**

- optimized for time-series workloads
- supports retention, tiering, and compression
- feeds low-latency UI reads and ad hoc queries

**How users interact with it**

- operators browse trends and alarms
- analysts run SQL queries and export CSV
- engineers replay past data windows for testing

### Historian SQL workflow

The SQL panel is the read-only historian analysis surface.

**What it does**

- lets operators and analysts run ad-hoc SQL against the historian tables
- validates the query before it reaches the database
- enforces a server-side timeout so large scans do not hang the browser indefinitely
- lets the user cancel an active statement from the UI

**Main inputs**

- a read-only SQL statement
- optional query parameters
- historian connection settings from the deployment environment

**Main outputs**

- tabular query results rendered in the UI
- CSV export for local analysis
- a query status message if the statement is canceled, fails, or times out

**How it performs**

- the query is executed on the historian service, not in the browser
- cancellation sends a stop request to the active PostgreSQL statement
- the timeout keeps accidental full-table scans bounded on the server

**How users interact with it**

- users type a historian-safe SQL statement into the editor
- a Cancel button appears while the query is running
- the result table shows rows and columns directly below the editor
- contextual `?` help tips explain where the data comes from and what the panel can and cannot do

### 7) UI and Operator Experience

This is the working surface for users.

**What it does**

- shows pipeline state, historian data, alarms, observability, and replay controls
- streams updates with WebSockets instead of refresh polling
- provides a dashboard builder, KPI builder, SQL query panel, and service links
- supports mobile-friendly layouts and live operational views

**Main inputs**

- WebSocket event streams
- REST API responses
- historian query results
- local dashboard preferences

**Main outputs**

- live charts
- alarm tables
- raw event tables
- trend views
- configurable operator dashboards

**How it performs**

- event-driven updates reduce wasteful refresh cycles
- panels update only when underlying data changes
- users can inspect raw data and summarized data from one place

**How users interact with it**

- operators use the dashboard for live monitoring
- analysts use SQL and KPI tools
- testers use replay and scenario controls
- admins use service links and configuration screens

### Contextual help tips

The UI now uses small `?` help tips on the most ambiguous surfaces.

**What it does**

- gives inline explanations without forcing the user to leave the page
- clarifies which panels are editable in the app and which are deployment-configured
- reduces confusion around SQL, replay, webhooks, notifications, and integration catalogs

**How users interact with it**

- hover or focus the `?` icon to read the explanation
- use the guidance to find the real owner screen or deployment file
- use the tip text to understand whether a panel is read-only, catalog-only, or editable

### 8) Notifications and Integrations

This is how the platform talks to the outside world.

**What it does**

- sends outbound webhooks for alarms and events
- supports notification channels such as email, Slack, Teams, and generic webhooks
- exposes REST APIs for ingest and integration
- supports outbound protocol bridges such as MQTT and AMQP

**Main inputs**

- alarms
- event triggers
- API requests
- configured destinations

**Main outputs**

- notification messages
- webhook deliveries
- integration API responses
- outbound bridge traffic

**How it performs**

- makes the platform usable inside a wider operations environment
- allows incident and workflow tools to react automatically
- supports both human notifications and machine-to-machine integration

### 9) Security and Governance

This is the control layer.

**What it does**

- manages users, roles, and tenant boundaries
- records audit events
- supports authentication and authorization foundations

**Main inputs**

- login requests
- role assignments
- protected API requests

**Main outputs**

- auth responses
- authorization decisions
- audit records

**How it performs**

- provides the minimum structure needed for shared deployments
- prepares the platform for open-source hardening and multi-user use

### 10) Observability

This is how the platform measures itself.

**What it does**

- exposes Prometheus metrics
- shows Grafana dashboards and health
- tracks throughput, latency, protocol mix, severity mix, and DLQ activity

**Main inputs**

- service metrics from edge, AI gateway, broker, and APIs

**Main outputs**

- live charts
- platform health indicators
- benchmark and soak-test measurements

**How it performs**

- makes performance bottlenecks visible
- helps validate whether the platform stays responsive under load
- supports both developer debugging and operator monitoring

## Asset Model

The platform uses an industrial hierarchy so data is organized like a plant instead of like a random sensor list.

**Hierarchy**

- site
- area
- line
- cell
- asset
- tag

**Tag metadata**

- unit
- min and max
- warning and critical limits
- sampling rate

**Configuration**

- `config/assets.yaml`

This model improves readability, rules, historian views, alert routing, and future deployment mapping.

## What users and systems send in

The platform accepts several kinds of input:

- live protocol data from OPC UA, MQTT, Modbus TCP, and Modbus RTU
- replayed CSV and maintenance datasets
- business events from CDC
- manual API ingestion calls
- scenario settings from UI, env vars, or CLI
- dashboard and KPI configuration from the frontend

## What the platform sends out

The platform produces several kinds of output:

- Kafka-compatible streaming topics
- historian records
- alarms and event streams
- AI summaries
- observability metrics
- SQL query results and CSV exports
- webhook and notification deliveries
- operator-facing dashboards and reports

## How people use the platform

### Operators

- watch alarms, trends, and live status
- follow AI summaries to understand abnormal behavior
- use the historian to inspect what just happened

### Engineers

- configure assets, tags, scenarios, and thresholds
- run replay jobs and soak tests
- connect the platform to external systems

### Analysts

- query historian data with SQL
- build KPIs and dashboards
- compare expected faults against detected faults

### Developers

- add connectors, analytics, and integrations
- benchmark services and inspect metrics
- test features without real plant hardware

## Current maturity

Right now the platform is strong as a local industrial streaming lab and demo environment.

It already covers:

- ingestion
- normalization
- analytics
- historian
- AI summaries
- observability
- live UI
- notifications
- integration APIs

The next major step is distribution hardening: packaging, installation flows, update strategy, offline deployment support, and open-source release quality.

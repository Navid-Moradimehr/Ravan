# Feature Audit Report

**Date**: 2026-07-01
**Total Features**: 98
**Implemented**: Core platform and rollout scaffolding are broadly implemented
**Status**: Strong local/open-source foundation, but not every advanced feature area is production-complete.

This file records the broad feature surface that exists in the repo.
For a stricter view of what is production-ready versus only foundational,
see `docs/model-agent-roadmap.md` and `docs/multi-site-rollout.md`.
For the current complete/incomplete production checklist, see `docs/production-readiness-checklist.md`.

## Implemented Categories

### Core Streaming (10/10)
- Multi-protocol ingestion (OPC UA, MQTT, Modbus TCP, Modbus RTU)
- Protocol simulators + real hardware connectors
- Canonical event normalization
- Schema versioning
- Dead-letter queue (DLQ)
- Real-time stream processing (Flink)
- Rolling window analytics
- Anomaly scoring
- Severity classification
- Exactly-Once Processing (idempotent producer, acks=all)

### AI Gateway (4/4)
- Provider-neutral AI gateway support for OpenAI-compatible and open-weight backends
- Deterministic fallback
- LLM batching
- Latency metrics (p95)

### Data Pipeline (6/6)
- CDC pipeline (PostgreSQL → Debezium → Redpanda)
- Dataset replay engine
- AI4I 2020 adapter
- Generic CSV replayer
- Stream Replay & Time Travel (timestamp window filtering)
- Real-time Data Preview (peek into Kafka topics without consuming offsets)

### Scenario Engine (4/4)
- 8 reusable scenarios (normal, drift, spike, stuck, dropout, noisy, degradation, maintenance)
- Environment variable configuration
- CLI flag configuration
- Ground-truth severity labels

### Asset Model (3/3)
- Full hierarchy (site → area → line → cell → asset → tag)
- Tag metadata (unit, min/max, limits, sampling rate)
- config/assets.yaml configuration

### Analytics (9/9)
- Configurable rule-based scoring
- Rolling z-score detection
- EWMA detection
- Rate-of-change detection
- Stuck-value detection
- Known vs detected fault evaluation
- Evaluation metrics (precision, recall, F1)
- Trainable Anomaly Detection (PyOD: IForest, LOF, OCSVM)
- Predictive maintenance model training foundation

### Historian (10/10)
- TimescaleDB storage
- ClickHouse option
- Schema registry validation
- WebSocket streaming (replaced SSE)
- Asset hierarchy tree UI
- Trend charts
- Alarms table
- Raw events table
- Data retention & tiering policies (hot/warm/cold)
- Data compression for TimescaleDB chunks

### Observability (3/3)
- Prometheus + Grafana
- Custom metrics (throughput, latency, protocol mix, severity mix, DLQ)
- Next.js dashboard with live charts

### UI Features (8/8)
- Event-driven WebSocket streaming (no polling)
- Scenario & replay controls
- Asset hierarchy browser
- Trend visualization
- Operator links to all services
- Mobile-responsive layout
- Custom dashboard builder (localStorage persistence, reorder panels)
- SQL query interface with CSV export
- KPI Builder (create calculated metrics from raw tags)

### API & Integration (12/12)
- REST API (FastAPI)
- Webhook outbound system
- Webhook test functionality
- Notification system (email/Slack/Teams/webhook)
- REST API full CRUD for external systems (/api/v1/events/ingest)
- MQTT/AMQP outbound bridge
- Connector Marketplace (12 pre-built connectors)
- Schema Registry UI + validation API
- Visual Pipeline Designer backend (DAG nodes/edges)
- Digital Twin Integration (3D scene graph, entity mapping)
- Shift/Production Reporting (OEE: availability, performance, quality)
- Collaboration features (annotations on events/alarms)

### Security (5/5)
- RBAC (Role-Based Access Control)
- Audit logging
- User management API
- Authentication endpoint
- Multi-tenancy foundation (Tenant model, namespace isolation)

### Data Sources (7/7)
- AI4I 2020 catalog entry
- NASA Bearing Dataset catalog entry
- NASA C-MAPSS catalog entry
- SKAB catalog entry
- NAB catalog entry
- SWaT/WADI catalog entry
- Built-in mock generator

### Deployment (1/1)
- Kubernetes Helm chart with profiles (dev, demo, edge, prod)
- Docker Compose for local development
- Auto-scaling configuration in values.yaml

## Remaining Gaps

The repo has wide feature coverage, but these areas still need additional implementation or hardening before they should be considered industry-standard production features:

- embeddings and retrieval backend
- model evaluation lifecycle and promotion workflow
- future diagnostic-agent runtime
- future supervised action-agent runtime
- production packaging and installer maturity
- stronger security hardening for shared multi-user deployments
- per-site production benchmarking on target database and model topologies

The following foundation already exists and should be treated as infrastructure, not a finished agent product:

- model registry and role-based model config
- prompt/version registry
- structured response validation
- read-only tool schemas
- read-only context package assembly
- deterministic retrieval/search boundary for historian, alarms, assets, reports, and scenarios

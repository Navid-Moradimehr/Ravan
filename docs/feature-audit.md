# Feature Audit Report

**Date**: 2026-06-28
**Total Features**: 98
**Implemented**: 65 (66.3%)
**Status**: Core platform complete. Production hardening and advanced analytics remaining.

## Implemented Categories (65 features)

### Core Streaming (9/9)
- Multi-protocol ingestion (OPC UA, MQTT, Modbus)
- Protocol simulators (no hardware needed)
- Canonical event normalization
- Schema versioning
- Dead-letter queue (DLQ)
- Real-time stream processing (Flink)
- Rolling window analytics
- Anomaly scoring
- Severity classification

### AI Gateway (4/4)
- OpenAI-compatible API support
- Deterministic fallback
- LLM batching
- Latency metrics (p95)

### Data Pipeline (4/4)
- CDC pipeline (PostgreSQL → Debezium → Redpanda)
- Dataset replay engine
- AI4I 2020 adapter
- Generic CSV replayer

### Scenario Engine (4/4)
- 8 reusable scenarios (normal, drift, spike, stuck, dropout, noisy, degradation, maintenance)
- Environment variable configuration
- CLI flag configuration
- Ground-truth severity labels

### Asset Model (3/3)
- Full hierarchy (site → area → line → cell → asset → tag)
- Tag metadata (unit, min/max, limits, sampling rate)
- config/assets.yaml configuration

### Analytics (7/7)
- Configurable rule-based scoring
- Rolling z-score detection
- EWMA detection
- Rate-of-change detection
- Stuck-value detection
- Known vs detected fault evaluation
- Evaluation metrics (precision, recall, F1)

### Historian (8/8)
- TimescaleDB storage
- ClickHouse option
- Schema registry validation
- WebSocket streaming (replaced SSE)
- Asset hierarchy tree UI
- Trend charts
- Alarms table
- Raw events table

### Observability (3/3)
- Prometheus + Grafana
- Custom metrics (throughput, latency, protocol mix, severity mix, DLQ)
- Next.js dashboard with live charts

### UI Features (6/6)
- Event-driven WebSocket streaming (no polling)
- Scenario & replay controls
- Asset hierarchy browser
- Trend visualization
- Operator links to all services
- Mobile-responsive layout

### API & Integration (6/6)
- REST API (FastAPI)
- Webhook outbound system
- Webhook test functionality
- Notification system (email/Slack/Teams/webhook)
- SQL query interface
- Custom dashboard builder

### Security (4/4)
- RBAC (Role-Based Access Control)
- Audit logging
- User management API
- Authentication endpoint

### Data Sources (7/7)
- AI4I 2020 catalog entry
- NASA Bearing Dataset catalog entry
- NASA C-MAPSS catalog entry
- SKAB catalog entry
- NAB catalog entry
- SWaT/WADI catalog entry
- Built-in mock generator

## Remaining Gaps (33 features)

### High Priority - Production Readiness
1. Real PLC/SCADA connectors (not just simulators)
2. TLS/mTLS for protocol connections
3. Data retention / tiering policies
4. Kubernetes Helm chart
5. Edge-to-cloud sync / federation

### Medium Priority - Feature Completeness
6. Report generation / scheduled exports
7. Alert escalation rules
8. Alert acknowledgment workflow with audit trail
9. Data compression for historian
10. Backup/restore for historian
11. User-defined KPIs / calculated tags
12. REST API full CRUD for external systems
13. MQTT/AMQP outbound bridge
14. Correlation analysis (multi-tag/root-cause)

### Lower Priority - Advanced Features
15. Predictive maintenance model training
16. Visual Pipeline Designer
17. Schema Registry UI
18. Real-time Data Preview (peek into topics)
19. Connector Marketplace
20. Stream Replay & Time Travel
21. Exactly-Once Processing Guarantees
22. Multi-Tenancy
23. Self-Service BI
24. KPI Builder
25. Trainable Anomaly Detection ML
26. Digital Twin Integration
27. Shift/Production Reporting (OEE)
28. Collaboration features
29. OPC UA client discovery/browse
30. Modbus RTU/serial support
31. MQTT Sparkplug B support
32. Auto-scaling for processing
33. Custom dashboard builder (fully functional panels)

## Open Source Research Needed

For each gap, we should research existing open-source solutions:

| Gap | Potential Open Source Solutions |
|-----|--------------------------------|
| Real PLC connectors | libplctag (C), snap7 (Python), pylogix |
| OPC UA discovery | python-opcua, asyncua |
| Modbus RTU | pymodbus (already has RTU) |
| MQTT Sparkplug B | tahu (Eclipse), sparkplug_b |
| Alert escalation | PagerDuty OSS alternatives, Prometheus Alertmanager |
| Data retention | TimescaleDB native compression, pg_partman |
| Backup/restore | pg_dump, wal-g, barman |
| TLS/mTLS | cert-manager, Let's Encrypt, step-ca |
| Kubernetes | Helm, Kustomize, ArgoCD |
| Edge-to-cloud | KubeEdge, EdgeX Foundry, Akri |
| Correlation analysis | pandas, dask, NetworkX for root-cause |
| Predictive maintenance | skforecast, darts, Prophet, TensorFlow/PyTorch |
| Trainable anomaly detection | PyOD, AnomalyDetection, Merlion (Salesforce) |
| Digital twin | Eclipse Ditto, Azure Digital Twins (not OSS) |
| OEE reporting | oee-toolkit, manufacturing analytics |
| Collaboration | Grafana annotations, Mattermost |

# Implementation Log

## 2026-06-28 - Phase 7 Complete + Quick Wins

### WebSocket Streaming (Phase 7)
- Replaced all HTTP polling with WebSocket streaming
- Added `/ws/alarms`, `/ws/events`, `/ws/telemetry` endpoints
- Background broadcasters with change-detection (only push when data changes)
- Auto-reconnect with 3s backoff
- Heartbeat every 15 seconds

### Benchmark Results
- 47 tests passing → 66 tests passing
- Full pipeline: 125,830 events/sec
- Real data (AI4I): 118,470 events/sec
- WebSocket streaming eliminates polling overhead

### Quick Wins Implemented (5 features)

1. **Modbus RTU Support**
   - File: `services/edge_ingest/modbus_rtu_client.py`
   - Extends existing pymodbus (zero new dependencies)
   - Device scanning across baudrates and slave IDs
   - Context manager support
   - 4 tests passing

2. **TLS for Local Development**
   - Files: `scripts/setup-local-tls.sh`, `scripts/setup-local-tls.ps1`
   - Uses mkcert (open-source by Filippo Valsorda)
   - Creates certificates for localhost, docker networks, simulators
   - TLS info endpoint at `/.well-known/tls-info`

3. **Apprise Notifications**
   - File: `services/api_service/notifications.py`
   - Supports 100+ notification channels (email, Slack, Teams, Discord, SMS)
   - Optional dependency (falls back to logging if not installed)
   - Environment variable configuration: `APPRISE_URLS`

4. **Backup/Restore**
   - File: `services/historian/backup.py`
   - Uses pg_dump/pg_restore (standard PostgreSQL tools)
   - Automatic timestamped backups
   - Backup listing with metadata
   - wal-g status check for production continuous archiving

5. **Correlation Analysis**
   - File: `services/analytics/correlation.py`
   - Pearson correlation matrices
   - Strong correlation detection (configurable threshold)
   - NetworkX graph-based root-cause analysis
   - Anomaly propagation detection
   - 5 tests passing

### Remaining Gaps: 28 (down from 33)

Closed:
- Data retention / tiering policies
- Alert acknowledgment workflow with audit trail
- Modbus RTU/serial support
- TLS/mTLS for protocol connections
- Backup/restore for historian
- Correlation analysis (multi-tag/root-cause)

Still open (28):
- Real PLC/SCADA connectors
- OPC UA client discovery/browse
- MQTT Sparkplug B support
- Report generation / scheduled exports
- Predictive maintenance model training
- Alert escalation rules
- Data compression for historian
- Kubernetes Helm chart
- Edge-to-cloud sync / federation
- Auto-scaling for processing
- Custom dashboard builder (fully functional)
- User-defined KPIs / calculated tags
- REST API full CRUD
- MQTT/AMQP outbound bridge
- Visual Pipeline Designer
- Schema Registry UI
- Real-time Data Preview
- Connector Marketplace
- Stream Replay & Time Travel
- Exactly-Once Processing Guarantees
- Multi-Tenancy
- Self-Service BI
- KPI Builder
- Trainable Anomaly Detection ML
- Digital Twin Integration
- Shift/Production Reporting (OEE)
- Collaboration features

## Real-world correctness review (2026-06-29)

Reviewed the live data path (edge ingest -> normalize -> processor -> historian) for correctness with real datasets, not just mock data. Found and fixed three issues that would have broken real-world operation.

### Fixed

1. **Edge protocol literal rejected non-edge producers (critical)**
   - `services/edge_ingest/model.py` `Protocol` was limited to `opcua/mqtt/modbus`.
   - Every `dataset`, `mock`, `sparkplug_b`, `modbus_rtu`, and `api` event failed Pydantic validation and was routed to the DLQ instead of into the pipeline.
   - Added all producer protocols to the literal so real-data replay, the mock generator, Sparkplug B, and Modbus RTU events validate and flow.

2. **Historian connection ignored `.env` (critical)**
   - `services/historian/client.py` read only `TIMESCALE_*` env vars, but `.env.example`/`.env` define `POSTGRES_*`.
   - Defaults silently won, pointing the historian at the wrong host/port.
   - Now reads `TIMESCALE_*` with `POSTGRES_*` fallback, matching `.env`.

3. **Processor dropped non-temperature/vibration/pressure tags (high)**
   - `normalize_runtime_event` collapsed every real tag into three legacy fields; any other tag was lost (value 0.0).
   - `score_event` only scored the three legacy fields.
   - Normalization now preserves the real `tag`, `value`, `unit`, asset id, and fault labels.
   - The processor's baseline detector now also scores the actual tag, so e.g. `RotationalSpeed` from AI4I gets anomaly detection instead of being ignored.

### Verified
- New regression tests: `tests/test_realworld_fixes.py` (11 tests).
- Full Python suite: 135 passed.

### Notes
- The processor's legacy-field scoring (temperature/vibration/pressure thresholds) is intentionally preserved for backward compatibility with existing dashboards and rule sets.

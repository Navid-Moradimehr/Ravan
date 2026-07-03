# Open Source Research for Remaining Gaps

## Date: 2026-06-28
## Purpose: Find existing open-source solutions to avoid reinventing the wheel

---

## 1. Real PLC/SCADA Connectors

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **libplctag** | C | MPL 2.0 | Rockwell/Allen-Bradley PLC communication |
| **snap7** | C/C++ | LGPL 3.0 | Siemens S7 protocol (Python wrapper: python-snap7) |
| **pylogix** | Python | MIT | Rockwell PLC (modern, actively maintained) |
| **OpenPLC** | C/C++ | GPL 3.0 | Full PLC runtime + protocol support |
| **mbedtls** | C | Apache 2.0 | For TLS on PLC connections |

**Recommendation**: Use `pylogix` for Rockwell, `python-snap7` for Siemens. Both are pip-installable.

---

## 2. OPC UA Discovery & Browse

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **python-opcua** | Python | LGPL 3.0 | Pure Python, mature |
| **asyncua** | Python | LGPL 3.0 | Asyncio-based, modern fork of python-opcua |
| **open62541** | C | MPL 2.0 | Most popular C OPC UA stack |

**Recommendation**: Use `asyncua` for Python services. Supports discovery, browsing, subscriptions.

---

## 3. Modbus RTU/Serial Support

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **pymodbus** | Python | BSD-3 | Already used for TCP, supports RTU/ASCII/UDP |
| **libmodbus** | C | LGPL 2.1 | Fast C library, Python bindings available |
| **minimalmodbus** | Python | Apache 2.0 | Simple RTU over serial |

**Recommendation**: Extend existing `pymodbus` usage to enable RTU mode. Zero new dependencies.

---

## 4. MQTT Sparkplug B

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **tahu** (Eclipse) | Java/JS | EPL 2.0 | Reference implementation from Eclipse |
| **sparkplug_b** | Python | MIT | Python protobuf implementation |
| **Chariot** | C | Apache 2.0 | C implementation for edge devices |

**Recommendation**: Use `sparkplug_b` Python package for protobuf encoding/decoding.

---

## 5. Alert Escalation & Notification

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **Prometheus Alertmanager** | Go | Apache 2.0 | Industry standard, supports routing, silencing |
| **Grafana OnCall** | Python/Go | AGPL 3.0 | Modern alternative to PagerDuty |
| **ntfy** | Go | Apache 2.0 | Simple pub/sub notifications |
| **Apprise** | Python | MIT | Universal notification library (100+ services) |

**Recommendation**: Use **Apprise** for notifications (covers email, Slack, Teams, Discord, etc.). Integrate Prometheus Alertmanager for escalation chains.

---

## 6. Data Retention & Compression

| Solution | Type | License | Notes |
|----------|------|---------|-------|
| **TimescaleDB native compression** | SQL | Apache 2.0 | Built-in, 90%+ compression |
| **pg_partman** | PostgreSQL | PostgreSQL | Automated partition management |
| **pg_dump / pg_restore** | PostgreSQL | PostgreSQL | Standard backup |
| **wal-g** | Go | Apache 2.0 | Continuous archiving for PostgreSQL |
| **barman** | Python | GPL 3.0 | PostgreSQL backup and recovery manager |

**Recommendation**: Enable TimescaleDB compression (single SQL command). Use `pg_partman` for automated retention policies.

---

## 7. TLS/mTLS

| Solution | Type | License | Notes |
|----------|------|---------|-------|
| **cert-manager** | Kubernetes | Apache 2.0 | Auto TLS for K8s |
| **step-ca** | Go | Apache 2.0 | Private CA, ACME server |
| **Let's Encrypt** | Service | Free | Public certificates |
| **mkcert** | Go | BSD | Local dev certificates |

**Recommendation**: Use `mkcert` for local development. For production, `step-ca` or `cert-manager`.

---

## 8. Kubernetes & Deployment

| Solution | Type | License | Notes |
|----------|------|---------|-------|
| **Helm** | YAML | Apache 2.0 | Package manager for K8s |
| **Kustomize** | YAML | Apache 2.0 | Native K8s config management |
| **ArgoCD** | Go | Apache 2.0 | GitOps continuous delivery |
| **Docker Compose** | YAML | Apache 2.0 | Already used, good for dev |

**Recommendation**: Create Helm chart for production. Keep Docker Compose for dev.

---

## 9. Edge-to-Cloud Sync

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **KubeEdge** | Go | Apache 2.0 | K8s native edge orchestration |
| **EdgeX Foundry** | Go | Apache 2.0 | Full IoT edge platform |
| **Akri** | Rust | Apache 2.0 | K8s device discovery for edge |
| **Mosquitto bridge** | C | EPL 2.0 | MQTT broker-to-broker sync |

**Recommendation**: Use Mosquitto MQTT bridge for simple edge-to-cloud. Evaluate KubeEdge for full K8s edge.

---

## 10. Correlation Analysis & Root Cause

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **pandas** | Python | BSD-3 | Data manipulation, correlation matrices |
| **dask** | Python | BSD-3 | Parallel pandas for large datasets |
| **NetworkX** | Python | BSD-3 | Graph-based root-cause analysis |
| **pgmpy** | Python | MIT | Probabilistic graphical models (Bayesian networks) |
| **causalnex** | Python | Apache 2.0 | Causal inference from Microsoft |

**Recommendation**: Use **pandas** for correlation matrices. Use **pgmpy** or **causalnex** for advanced root-cause analysis.

---

## 11. Predictive Maintenance & ML

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **skforecast** | Python | BSD-3 | Time series forecasting with scikit-learn |
| **darts** | Python | Apache 2.0 | Multiple forecasting models (N-BEATS, TCN, etc.) |
| **Prophet** | Python/R | MIT | Facebook's forecasting tool |
| **PyOD** | Python | BSD-2 | Python Outlier Detection (30+ algorithms) |
| **Merlion** | Python | BSD-3 | Salesforce's ML for time series (anomaly + forecast) |
| **TensorFlow** | Python/C++ | Apache 2.0 | Deep learning for advanced models |
| **PyTorch** | Python/C++ | BSD | Deep learning for research |

**Recommendation**: 
- **Merlion** for unified anomaly detection + forecasting (covers both use cases)
- **PyOD** for extensive outlier detection algorithms
- **skforecast** for simple, interpretable forecasting
- **darts** for deep learning-based forecasting (N-BEATS, N-HiTS)

**Transfer Learning Models**:
- Use pre-trained models from **Hugging Face** (time-series-transformers)
- Fine-tune on user's historical data
- Export models to ONNX for edge deployment

---

## 12. Digital Twin

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **Eclipse Ditto** | Java/JS | EPL 2.0 | Full digital twin framework |
| **Azure Digital Twins** | Service | Commercial | Not open source |
| **AWS IoT TwinMaker** | Service | Commercial | Not open source |
| **ThingsBoard** | Java | Apache 2.0 | IoT platform with rule engine |

**Recommendation**: Use **Eclipse Ditto** for open-source digital twin. Integrates with MQTT/Kafka.

---

## 13. OEE & Production Reporting

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **oee-toolkit** | Python | MIT | OEE calculation library |
| **manufacturing-analytics** | Python | MIT | Production metrics |

**Recommendation**: Build OEE calculator using simple formulas. Availability × Performance × Quality.

---

## 14. Collaboration & Annotations

| Solution | Language | License | Notes |
|----------|----------|---------|-------|
| **Grafana annotations** | Go/TS | AGPL 3.0 | Built-in dashboard annotations |
| **Mattermost** | Go/TS | MIT | Open-source Slack alternative |
| **Zulip** | Python/JS | Apache 2.0 | Threaded team chat |

**Recommendation**: Use Grafana annotations for event marking. Integrate Mattermost for team alerts.

---

## 15. Exactly-Once Processing

| Solution | Type | License | Notes |
|----------|------|---------|-------|
| **Kafka transactions** | Java | Apache 2.0 | Built into Kafka |
| **Redpanda** | C++ | BSL | Kafka-compatible, supports transactions |
| **Flink checkpointing** | Java | Apache 2.0 | Exactly-once with Kafka |

**Recommendation**: Enable Flink checkpointing with Kafka transactions. Already partially supported.

---

## Summary: Top 10 Quick Wins

| Priority | Feature | Open Source Solution | Effort |
|----------|---------|---------------------|--------|
| 1 | Data retention | TimescaleDB compression | Low |
| 2 | Notifications | Apprise | Low |
| 3 | Alert escalation | Prometheus Alertmanager | Medium |
| 4 | Modbus RTU | pymodbus (already used) | Low |
| 5 | TLS for dev | mkcert | Low |
| 6 | Backup | wal-g | Medium |
| 7 | Predictive ML | PyOD + skforecast | Medium |
| 8 | Correlation | pandas + NetworkX | Low |
| 9 | OPC UA discovery | asyncua | Medium |
| 10 | Kubernetes | Helm chart | Medium |

## Current Edge Compatibility Direction

The codebase already supports OPC UA, MQTT, Modbus TCP, Modbus RTU, and Sparkplug B at the ingest layer.
The next compatibility step should be gateway-first support for EtherNet/IP and PROFINET rather than trying to
reimplement vendor stacks inside the core service.

That approach keeps the platform compatible with a broader set of PLC families while preserving a stable internal
event contract for historian, analytics, and multi-site rollout.

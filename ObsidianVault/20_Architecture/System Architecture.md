# System Architecture

```text
Ingestion           Broker             Processing          Insight
---------           ------             ----------          -------
Mock IoT  ────────> Redpanda ────────> PyFlink ─────────> AI Gateway
Postgres ─Debezium> CDC topics         window rules        LLM summaries
```

## Components

- Redpanda provides Kafka-compatible topics and local schema registry capability.
- PyFlink owns stateful windowing and anomaly detection.
- FastAPI AI Gateway owns OpenAI-compatible LLM calls and async batching.
- Prometheus and Grafana expose platform health and latency.
- Next.js dashboard provides a control-room view over the local platform.

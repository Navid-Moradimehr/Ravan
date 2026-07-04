# System Architecture

```text
Ingestion           Broker             Processing                     Insight
---------           ------             ----------                     -------
Mock IoT  --> Kafka --> PyFlink / Python fallback --> AI Gateway
Postgres --> Debezium --> CDC topics   keyed state + rules            LLM summaries
```

## Components

- Kafka provides the broker layer and the platform keeps schema validation inside application code.
- PyFlink owns the distributed keyed-state runtime path.
- The Python processor stays available as the local fallback and benchmark harness with the same enrichment contract.
- FastAPI AI Gateway owns OpenAI-compatible and open-weight LLM calls with async batching.
- Prometheus and Grafana expose platform health and latency.
- Next.js dashboard provides a control-room view over the local platform.

# Ravan

## Goal

Create a local-first real-time streaming and BI platform that combines capabilities inspired by CGR/GITA Streaming and BI: ingestion, stream processing, CDC, dashboards, and AI-assisted explanations.

## Success Criteria

- A generated IoT event can be produced, processed, enriched, and observed locally.
- PostgreSQL `orders` changes are captured through Debezium.
- Operators can inspect throughput, lag, LLM latency, and service health.
- The AI provider can switch between LM Studio and cloud OpenAI-compatible endpoints through environment variables.

## Links

- [[../20_Architecture/System Architecture]]
- [[../30_UI_UX/Dashboard Design Direction]]
- [[../40_Runbooks/Local Development]]

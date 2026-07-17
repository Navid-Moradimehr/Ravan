
### Product Requirements Document (PRD): "Ravan" (Inspired by GITA Stream)

#### 1. Overview
The goal is to build a real-time data processing engine that replicates the core capabilities of GITA Stream: low-latency ingestion, stateful stream processing, and AI-driven insights [1, 2]. This version will be optimized for local development on WSL2 (Ubuntu) with NVIDIA GPU acceleration for LLM tasks.

#### 2. Technical Stack
   Message Broker: Redpanda (A C++-based, Kafka-compatible broker mentioned in the sources as a high-performance alternative to Apache Kafka, ideal for local environments due to its low resource footprint) [2-4].
   Stream Processing: Apache Flink or ksqlDB for real-time SQL-like transformations [1, 3, 5].
   CDC (Change Data Capture): Debezium to monitor local database changes [6, 7].
   AI/LLM Layer: Python-based services connecting to LM Studio (Local) or Cloud APIs (OpenAI/Anthropic) using LangChain or LlamaIndex.
   Infrastructure: Docker Compose on WSL2 for containerization.
   Observability: Prometheus and Grafana for monitoring throughput and lag [3, 8].
   Storage: MinIO (Local S3-compatible) for Tiered Storage simulation [8].

#### 3. Core Components
   Ingestion Layer: MQTT Broker bridge (for IoT data simulation) and Kafka Connect for DB ingestion [2, 9].
   Processing Layer: Stateful windowing logic to detect patterns (e.g., fraud or equipment failure) in sub-100ms [1, 10].
   AI Gateway: A service that consumes processed streams and sends them to your local LLM (running on your 4060 GPU via LM Studio) for real-time summarization or anomaly explanation.
   Mock Data Generator: A Python script to simulate high-velocity enterprise data (Financial transactions, IoT sensor logs, etc.) [10, 11].

#### 4. Hardware/Environment Configuration
   OS: Ubuntu on WSL2.
   GPU: NVIDIA 4060 (8GB VRAM) dedicated to LM Studio for hosting models like Llama-3 or Mistral.
   Connectivity: The app must use a configurable BASE_URL to toggle between http://localhost:1234/v1 (LM Studio) and cloud provider endpoints.

---

### Master Prompt for Codex CLI

You can use the following prompt to initialize your project structure and core logic.

"Act as a Senior Data Architect. Build a real-time streaming platform inspired by GITA Stream on Ubuntu/WSL2. 

System Requirements:
1. Use Docker Compose to orchestrate Redpanda (Kafka-compatible), Apache Flink, and a PostgreSQL database.
2. Implement a Python-based 'Stream-to-LLM' service. This service must:
   - Subscribe to a Redpanda topic.
   - Batch incoming messages every 5 seconds.
   - Send the batch to a local LLM via an OpenAI-compatible API (LM Studio at localhost:1234).
   - Support a fallback to cloud-based LLM models via environment variables.
3. Include a 'Mock Data Generator' script that produces JSON payloads representing industrial IoT sensors (temperature, vibration, pressure) at a rate of 100 messages/sec.
4. Integrate Debezium for CDC, monitoring changes in the PostgreSQL 'orders' table and streaming them to Redpanda.
5. Setup a Grafana dashboard configuration to monitor 'Consumer Lag' and 'Messages Per Second'.

Stack: 
- Backend: Python 3.10+, FastAPI
- Streaming: Redpanda (Dockerized)
- Processing: PyFlink
- Database: PostgreSQL with Debezium
- LLM: Local (LM Studio) + Cloud compatibility

Project Structure:
- /docker: compose files and configs
- /services/ingestion: Mock generator & CDC config
- /services/processor: Flink jobs
- /services/ai_gateway: LLM integration logic
- /scripts: setup and test scripts

Please generate the directory structure and the core Docker Compose file first."

### Testing with Mock Data & GPU
1.  Local LLM Setup: LM Studio is open on my system. you can find models there that are current;y available on http://172..17.0.1:1234  . i prefere openai/gpt-oss-20B


2.  Mock Data: The sources emphasize the importance of "Exactly-Once" semantics and "Schema Evolution" [9, 13]. Ensure your mock generator uses a Schema Registry (included in Redpanda) to maintain data integrity as you test [3, 5].
3.  Performance: Since GITA Stream targets sub-100ms latency, monitor your 4060's VRAM usage to ensure the LLM inference doesn't bottleneck the ingestion pipeline [1, 6]. Use the Python service to handle "Asynchronous Inference" so the stream doesn't stall while waiting for the LLM.

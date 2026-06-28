# Benchmark Results

## Test Environment
- **Date**: 2026-06-28
- **Platform**: Local Stream Engine (Python 3.11, Windows/WSL2)
- **Hardware**: Single-node development machine
- **Broker**: Redpanda (Kafka-compatible)
- **Historian**: TimescaleDB

## Test Suite Results

| Test Category | Tests | Status |
|---------------|-------|--------|
| AI4I Adapter | 2 | 2 passed |
| Analytics | 10 | 10 passed |
| Assets | 4 | 4 passed |
| Dataset Replayer | 3 | 3 passed |
| Edge Model | 4 | 4 passed |
| Historian | 2 | 2 passed |
| Mock Generator | 6 | 6 passed |
| Processor Normalization | 2 | 2 passed |
| Scenarios | 12 | 12 passed |
| UI Telemetry | 3 | 3 passed |
| **Total** | **47** | **47 passed** |

## Performance Benchmarks

### Component Throughput

| Component | Throughput | Events/Operations |
|-----------|-----------|-------------------|
| Mock Data Generation | 1,803 events/sec | 10,000 events in 5.55s |
| Full Pipeline (scenario + normalize + rules + baseline) | **125,830 events/sec** | 10,000 events in 0.079s |
| Scenario Engine Mutations | 1,698,717 mutations/sec | 10,000 mutations in 0.006s |
| Baseline Detection (z-score, EWMA, ROC, stuck) | 212,912 updates/sec | 10,000 updates in 0.047s |
| Event Normalization | 18,433,186 normalizations/sec | 10,000 normalizations in 0.001s |
| JSON Serialization | 329,195 serializations/sec | 100,000 serializations in 0.304s |
| Rule Evaluation | 571,968 evals/sec | 10,000 evaluations in 0.017s |

### Memory Efficiency

| Metric | Value |
|--------|-------|
| Average event size | 387 bytes |
| Memory for 10,000 events | 3.69 MB |
| Memory per event | ~0.38 KB |

### WebSocket Streaming

| Metric | Before (HTTP Polling) | After (WebSocket) | Improvement |
|--------|----------------------|-------------------|-------------|
| UI Update Method | HTTP polling every 2-5s | Event-driven push | Eliminated polling overhead |
| Connection Type | New HTTP connection per request | Persistent bidirectional | Reduced connection overhead |
| Data Transfer | Full dataset each poll | Only changed data | Reduced bandwidth |
| Reconnection | Manual refresh | Auto-reconnect (3s backoff) | Better resilience |
| Server Load | High (frequent DB queries) | Low (change-detection broadcast) | Reduced server load |

## Industry Comparison

| Platform | Throughput | Latency | Notes |
|----------|-----------|---------|-------|
| Apache Kafka (theoretical max) | 2M+ msgs/sec | <10ms p99 | Bare metal, tuned |
| Redpanda (this project's broker) | 1M+ msgs/sec | <5ms p99 | C++ implementation |
| MQTT brokers (HiveMQ/EMQX) | 1M+ msgs/sec | <5ms | IoT-optimized |
| Typical Industrial SCADA | 1K-10K tags/sec | 100ms-1s | Legacy protocols |
| **Local Stream Engine (full pipeline)** | **125K events/sec** | N/A | Python, single-node |
| **Local Stream Engine (mock generation)** | 1.8K events/sec | N/A | I/O bound (sleep-based) |

## Key Findings

1. **Full pipeline throughput of 125K events/sec** is excellent for a Python-based single-node validation stack
2. **Mock generation is I/O bound** at ~1,800/sec due to sleep-based rate limiting; processing is CPU-bound at 125K+/sec
3. **WebSocket streaming successfully eliminated all HTTP polling** in the UI
4. **All 47 tests pass** with no regressions
5. **Memory footprint is efficient**: ~0.38 KB per event

## Bottlenecks Identified

1. **Mock generation rate**: Sleep-based timing limits to ~1,800/sec. For higher throughput, use batch generation or remove sleep delays.
2. **JSON serialization**: 329K/sec is good but could be improved with orjson (10x faster) or msgpack.
3. **Database writes**: Not benchmarked yet. TimescaleDB insert performance depends on batch size and indexing.

## Recommendations

1. Use `orjson` instead of `json` for serialization (10x faster)
2. Batch historian inserts (100-1000 events per transaction)
3. Enable TimescaleDB compression for long-term storage
4. Consider uPlot for chart rendering (10x faster than Recharts SVG)

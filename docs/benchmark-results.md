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

## Refactor Impact

The current refactor pass changed the runtime shape of the platform:

- shared anomaly scoring now lives in `services/processor/scoring.py`
- historian writes are batched in the edge ingest and runtime processor paths
- the service Dockerfiles now copy the full `services/` tree so imports resolve in containers
- a local mixed-protocol benchmark pack was added at `data/benchmarks/industrial_mixed_benchmark.csv`

Expected effect:

- lower write amplification on TimescaleDB under sustained ingest
- fewer duplicate scoring rules to maintain across processing paths
- lower container boot risk from missing package imports

This is a structural performance improvement. The live end-to-end historian
throughput should be remeasured after deploying the batched write path before
making any production sizing claim.

### Mixed Replay Benchmark

Command:

```bash
python scripts/benchmark_mixed_replay.py --events 100000 --batch-size 256
```

Latest local run on the current codebase:

| Metric | Value |
|--------|-------|
| Events | 100,000 |
| Invalid events | 0 |
| Batches | 391 |
| Batch size | 256 |
| Elapsed | 1.4962s |
| Throughput | 66,835 events/sec |
| Serialized bytes | 40,112,500 |

Batch-size sweep on the same pack:

| Batch size | Throughput | Batches |
|-----------|------------|---------|
| 64 | 64,237 events/sec | 782 |
| 256 | 64,093 events/sec | 196 |
| 1024 | 63,756 events/sec | 49 |

Interpretation:

- CPU-path throughput is stable across the tested batch sizes.
- 256 is a sensible default because it reduces flush count without hurting throughput on this workload.
- The live DB writer still needs an on-container TimescaleDB measurement before the historian path can be sized for production.

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
3. **Mixed replay throughput is ~64K-69K events/sec** on the current benchmark pack, with 256 chosen as the default batch size
4. **WebSocket streaming successfully eliminated all HTTP polling** in the UI
5. **All 47 tests pass** with no regressions
6. **Memory footprint is efficient**: ~0.38 KB per event

## Bottlenecks Identified

1. **Mock generation rate**: Sleep-based timing limits to ~1,800/sec. For higher throughput, use batch generation or remove sleep delays.
2. **JSON serialization**: 329K/sec is good but could still be improved with orjson or msgpack in the non-API hot paths.
3. **Database writes**: historian writes now batch by default in the ingest and processor paths, but live TimescaleDB throughput should be remeasured after deployment.

## Recommendations

1. Use `orjson` instead of `json` for serialization in any remaining hot paths
2. Re-run live historian benchmarks after batching changes and tune batch size against the target TimescaleDB topology
3. Enable TimescaleDB compression for long-term storage
4. Consider uPlot for chart rendering (10x faster than Recharts SVG)

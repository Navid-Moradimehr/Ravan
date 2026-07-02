# Benchmark Results

## Test Environment
- **Date**: 2026-06-30
- **Platform**: Local Stream Engine (Python 3.11, Windows/WSL2)
- **Hardware**: Single-node development machine
- **Broker**: Redpanda (Kafka-compatible)
- **Historian**: TimescaleDB

## Latest Hardening Run

- **Date**: 2026-07-02
- **Scope**: historian query guardrails, auth defaults, Kafka producer caching, manual consumer commits, and vault tracking

### Targeted Regression Checks

| Check | Result |
|-------|--------|
| `python -m compileall services tests` | passed |
| Focused unit/regression tests | 23 passed |
| Historian table allowlist | passed |
| JWT default-secret visibility | passed |
| Kafka producer cache | passed |
| Manual consumer offset commit | passed |

### Latest Mock Benchmarks

| Benchmark | Value |
|-----------|-------|
| Deployment pack export rate | 728.91 files/sec |
| Deployment pack replay rate | 64,775.69 events/sec |
| Deployment pack matrix average export rate | 718.80 files/sec |
| Deployment pack matrix average replay rate | 61,813.35 events/sec |
| Mixed replay throughput | 58,548.76 events/sec |

### Real-World Simulator Benchmark

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark real-world-simulator --events 20 --batch-size 4 --cases mock-normal,industrial-benchmark
```

Latest local run on the current codebase:

| Case | Source | Scenario | Events/sec | Batches | Invalid events |
|------|--------|----------|------------|---------|----------------|
| mock-normal | mock-generator | normal | 12,181.75 | 5 | 0 |
| industrial-benchmark | data/benchmarks/industrial_mixed_benchmark.csv | mixed | 54,303.57 | 5 | 0 |
| **Average** | - | - | **33,242.66** | - | - |

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
| Events | 10,000 |
| Invalid events | 0 |
| Batches | 40 |
| Batch size | 256 |
| Elapsed | 0.1825s |
| Throughput | 54,779.87 events/sec |
| Serialized bytes | 4,011,250 |

Batch-size sweep on the same pack:

| Batch size | Throughput | Batches |
|-----------|------------|---------|
| 64 | 64,237 events/sec | 782 |
| 256 | 59,629 events/sec | 391 |
| 1024 | 63,756 events/sec | 49 |

Interpretation:

- CPU-path throughput is stable across the tested batch sizes.
- 256 is still a sensible default because it reduces flush count without materially changing throughput on this workload.
- The live DB writer still needs an on-container TimescaleDB measurement before the historian path can be sized for production.

### AI Gateway Provider Benchmark

Command:

```bash
python scripts/benchmark_ai_gateway_mock.py --provider openai_compat --events 100000 --batch-size 64
python scripts/benchmark_ai_gateway_mock.py --provider ollama --events 100000 --batch-size 64
```

Latest local run on the current codebase:

| Provider | Events | Batches | Batch Size | Elapsed | Throughput | Avg Prompt Bytes | Avg Summary Bytes |
|----------|--------|---------|------------|---------|------------|------------------|-------------------|
| openai_compat | 100,000 | 1,563 | 64 | 0.6142s | 162,812.89 events/sec | 18,434.4 | 29.0 |
| ollama | 100,000 | 1,563 | 64 | 0.6935s | 144,191.18 events/sec | 18,434.4 | 29.0 |

Interpretation:

- The provider abstraction adds very little overhead compared with the mock transport.
- OpenAI-compatible and Ollama-style backends both work through the same industrial prompt path.
- Real model servers will be slower than this mock benchmark because inference time dominates transport and parsing overhead.

### Site Profile Soak

Command:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/site-profile-soak.ps1 -SiteProfile config/site-profiles/single-site.yaml -Seconds 60 -MqttRatePerSecond 100 -RecoveryService processor
powershell -ExecutionPolicy Bypass -File scripts/site-profile-soak.ps1 -SiteProfile config/site-profiles/plant-local.yaml -Seconds 60 -MqttRatePerSecond 100 -RecoveryService processor
powershell -ExecutionPolicy Bypass -File scripts/site-profile-soak.ps1 -SiteProfile config/site-profiles/federated.yaml -Seconds 60 -MqttRatePerSecond 100 -RecoveryService processor
```

Latest local run on the current codebase:

| Profile | Deployment Mode | Events Delta | Elapsed | Throughput | DLQ Delta | Adapter Errors Delta | AI Provider | AI Model |
|---------|-----------------|--------------|---------|------------|-----------|----------------------|-------------|----------|
| single-site.yaml | single-site | 189 | 64.0s | 2.95 events/sec | 0 | 0 | openai_compat | openai/gpt-oss-20B |
| plant-local.yaml | plant-local | 1,514 | 64.1s | 23.63 events/sec | 0 | 0 | ollama | mistral |
| federated.yaml | federated | 1,553 | 64.7s | 24.00 events/sec | 0 | 0 | vllm | mistralai/Mistral-7B-Instruct-v0.3 |

Interpretation:

- The release-gate path now passes on all three profile shapes.
- Backup and restore drills completed successfully for each profile.
- The live soak harness exercises host-run services from the site profile contract and restarts the processor mid-run without manual repair.
- The numbers are environment-specific and should be rerun on each target site before production sizing.

## Performance Benchmarks

### Component Throughput

| Component | Throughput | Events/Operations |
|-----------|-----------|-------------------|
| Mock Data Generation | 1,803 events/sec | 10,000 events in 5.55s |
| Full Pipeline (scenario + normalize + rules + baseline) | **125,830 events/sec** | 10,000 events in 0.079s |
| AI Gateway Provider Path (openai_compat, mock transport) | 162,813 events/sec | 100,000 events in 0.614s |
| AI Gateway Provider Path (ollama, mock transport) | 144,191 events/sec | 100,000 events in 0.694s |
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
3. **Mixed replay throughput stays in the ~55K-64K events/sec band** on the current benchmark pack, with 256 still a sensible default batch size
4. **AI gateway provider plumbing is fast enough that mock transport overhead stays below 1s for 100K events**
5. **The site-profile soak passed on single-site, plant-local, and federated profiles, with backup/restore drills green**
6. **WebSocket streaming successfully eliminated all HTTP polling** in the UI
7. **The targeted refactor verification slice passed 33 tests** with no regressions
8. **Memory footprint is efficient**: ~0.38 KB per event
9. **The runtime hardening pass kept the benchmark path in the same operating band** while adding safer defaults for self-hosted industrial rollout

## Bottlenecks Identified

1. **Mock generation rate**: Sleep-based timing limits to ~1,800/sec. For higher throughput, use batch generation or remove sleep delays.
2. **JSON serialization**: 329K/sec is good but could still be improved with orjson or msgpack in the non-API hot paths.
3. **Database writes**: historian writes now batch by default in the ingest and processor paths, but live TimescaleDB throughput should be remeasured after deployment.

## Recommendations

1. Use `orjson` instead of `json` for serialization in any remaining hot paths
2. Re-run live historian benchmarks after batching changes and tune batch size against the target TimescaleDB topology
3. Enable TimescaleDB compression for long-term storage
4. Consider uPlot for chart rendering (10x faster than Recharts SVG)

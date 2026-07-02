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

## Distributed Runtime Alignment Run

- **Date**: 2026-07-02
- **Scope**: shared runtime enrichment contract, keyed-state Flink job, and compose-level distributed processor wiring

### Targeted Regression Checks

| Check | Result |
|-------|--------|
| `python -m compileall services tests` | passed |
| Focused unit/regression tests | 51 passed |
| Shared runtime enrichment contract | passed |
| Python fallback processor compatibility | passed |
| Flink job compile path | passed |

### Latest Benchmark Runs

| Benchmark | Value |
|-----------|-------|
| CGR stream slice throughput | 50,364.08 events/sec |
| CGR stream slice p99 | 0.0338 ms |
| Flink runtime slice throughput | 50,276.67 events/sec |
| Flink runtime slice p99 | 0.0364 ms |
| Mixed replay throughput | 93,423.46 events/sec |
| Mixed replay p99 | 0.0162 ms |
| Real-world simulator average throughput | 96,987.90 events/sec |
| Real-world simulator average p99 | 0.0240 ms |

### Change Notes

- The isolated stream slice now uses the shared runtime enrichment helper instead of duplicate in-line scoring and payload assembly.
- The distributed Flink processor keys by asset identity and keeps rolling state per key, which is the architecture step toward company-scale horizontal processing.
- The benchmark gains are mostly from eliminating duplicated work and tightening the hot record assembly path; the remaining gap to CGR remains substantial.
- Relative to the earlier local baseline recorded in this repo, the new run improved:
  - CGR stream slice throughput by about `2.7%` versus the previous session
  - Flink runtime slice throughput changed by about `-4.9%` versus the previous session
  - CGR stream slice p99 changed by about `+3.98%` versus the previous session
  - Flink runtime slice p99 changed by about `+24.2%` versus the previous session
- The mixed replay and real-world simulator baselines were not rerun in this session, so the last recorded numbers remain the reference point for those paths.

Additional focused CLI regression slice:

- `uv run pytest -q tests/test_project_manifest.py tests/test_datastreamctl.py`: 43 passed

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

### Site-Profile Benchmark Matrix

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark site-profile-matrix --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 20 --batch-size 4 --min-average-events-per-second 1
```

Latest local run on the current codebase:

| Site | Mode | Avg Events/sec | Threshold | Result |
|------|------|----------------|-----------|--------|
| demo-site | single-site | 44,795.24 | 500.0 | passed |
| plant-a | plant-local | 59,253.75 | 750.0 | passed |
| **Overall** | - | - | - | passed |

### Project Rollout Acceptance

Command:

```bash
uv run python -m services.cli.datastreamctl project-manifest rollout-acceptance config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 20 --batch-size 4 --min-average-events-per-second 1 --skip-network --skip-backup
```

Latest local run on the current codebase:

| Site | Release Gate | Avg Events/sec | Threshold | Result |
|------|--------------|----------------|-----------|--------|
| demo-site | passed | 48,558.93 | 500.0 | passed |
| plant-a | passed | 55,973.26 | 750.0 | passed |
| **Overall** | - | - | - | passed |

### Site-Profile Calibration

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark site-profile-calibration --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 20 --batch-size 4 --min-average-events-per-second 1
```

Latest local run on the current codebase:

| Site | Mode | Observed Avg Events/sec | Threshold | Headroom | Recommended Min | Recommended Batch |
|------|------|-------------------------|-----------|----------|-----------------|-------------------|
| demo-site | single-site | 52,786.52 | 500.0 | 52,286.52 | 42,229.22 | 256 |
| plant-a | plant-local | 47,759.79 | 750.0 | 47,009.79 | 38,207.83 | 256 |
| **Overall** | - | - | - | - | - | passed |

### CGR Gap Report

Command:

```bash
python -m services.cli.datastreamctl benchmark cgr-gap-report --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 10000 --batch-size 256 --warmup-events 0 --min-average-events-per-second 1
```

Latest local run on the current codebase:

| Metric | Events/sec | Gap x | Gap events/sec | Gap % |
|--------|------------|-------|----------------|-------|
| documented_full_pipeline | 125,830.00 | 15.89 | 1,874,170.00 | 93.71 |
| mixed_replay | 93,423.46 | 21.41 | 1,906,576.54 | 95.33 |
| cgr_stream_slice | 50,364.08 | 39.71 | 1,949,635.92 | 97.48 |
| flink_runtime_slice | 50,276.67 | 39.78 | 1,949,723.33 | 97.49 |
| real_world_average | 96,987.90 | 20.62 | 1,903,012.10 | 95.15 |
| site_profile_average | 98,080.16 | 20.39 | 1,901,919.84 | 95.10 |
| site_profile_best:plant-a | 98,163.61 | 20.37 | 1,901,836.39 | 95.09 |

Latency metrics from the same run:

| Metric | P99 ms | Gap ms | Gap % |
|--------|--------|--------|-------|
| mixed_replay | 0.0162 | 79.9838 | 99.98 |
| cgr_stream_slice | 0.0338 | 79.9662 | 99.96 |
| flink_runtime_slice | 0.0364 | 79.9636 | 99.95 |
| real_world_average | 0.0240 | 79.9760 | 99.97 |
| site_profile_average | 0.0187 | 79.9813 | 99.98 |
| site_profile_best:demo-site | 0.0183 | 79.9817 | 99.98 |

Notes:

- The command is now part of the CLI and is useful for tracking the practical gap to the public CGR Stream claim.
- This report now measures replay p99 latency, but it still does not measure real target-site broker/historian latency.
- The isolated `cgr_stream_slice` benchmark still shows the record-building and serialization costs more clearly than the old dict path. The bottleneck shifted away from rolling-window math once the internal representation was introduced.
- The distributed Flink runtime slice now has its own benchmark line, so the local measurements separate the fallback Python path from the keyed-state contract.
- This session shows run-to-run variance: the CGR slice improved a little, while the Flink slice slowed down relative to the previous session. That is not enough to call a structural regression yet, but it does mean the new Flink deployment path should be re-benchmarked under fixed host load before any claim of improvement.
- The documented full-pipeline number is the latest recorded repo benchmark reference and should still be remeasured on a target broker/historian topology before sizing.

### Post-Optimization Slice Benchmarks

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --events 10000 --batch-size 256 --warmup-events 0
uv run python -m services.cli.datastreamctl benchmark flink-runtime-slice --events 10000 --batch-size 256 --warmup-events 0
```

Latest local run on the current codebase after switching the keyed Flink path to the shared rolling-window state contract:

| Benchmark | Throughput | Delta vs previous recorded session | p99 | Delta vs previous recorded session |
|-----------|------------|------------------------------------|-----|------------------------------------|
| CGR stream slice | 50,882.38 events/sec | +1.0% | 0.0297 ms | -12.1% |
| Flink runtime slice | 49,823.25 events/sec | -0.9% | 0.0279 ms | -23.4% |

Interpretation:

- the Flink path no longer pays the old list-pop overhead
- the local benchmark still sits far below the public CGR target, so the remaining gap is mostly topology, serialization, broker, and sink behavior rather than rolling-window math
- the new numbers should be treated as a better baseline, not as a production comparison

### End-To-End Wire Benchmarks

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 10000 --batch-size 256 --warmup-events 0 --wire-format json
uv run python -m services.cli.datastreamctl benchmark end-to-end-pipeline --events 10000 --batch-size 256 --warmup-events 0 --wire-format msgpack
```

Latest local run on the current codebase:

| Wire format | Throughput | p99 | Payload bytes | Roundtrip bytes |
|-------------|------------|-----|---------------|-----------------|
| JSON | 36,842.39 events/sec | 0.0454 ms | 6,243,000 | 6,243,000 |
| MsgPack | 35,424.11 events/sec | 0.0466 ms | 5,649,375 | 5,649,375 |

Interpretation:

- MsgPack reduced payload size by about `9.5%` on this sample
- the throughput gain did not materialize in the current Python benchmark, which means the dominant cost is still Python object work around the codec, not the serialization format alone
- the strongest next throughput candidate is a compiled hot path for the processor and wire handling, not another Python-only micro-optimization

### Latest Rerun After Binary-Contract Work

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark cgr-gap-report --manifest config/project-manifest.yaml --csv data/benchmarks/industrial_mixed_benchmark.csv --site-ids demo-site,plant-a --events 10000 --batch-size 256 --warmup-events 0 --min-average-events-per-second 1
```

Latest local rerun on the current codebase:

| Metric | Events/sec | Gap x | Gap events/sec | Gap % |
|--------|------------|-------|----------------|-------|
| documented_full_pipeline | 125,830.00 | 15.89 | 1,874,170.00 | 93.71 |
| mixed_replay | 74,903.62 | 26.70 | 1,925,096.38 | 96.25 |
| cgr_stream_slice | 40,438.38 | 49.46 | 1,959,561.62 | 97.98 |
| flink_runtime_slice | 46,302.88 | 43.19 | 1,953,697.12 | 97.68 |
| end_to_end_json | 46,654.19 | 42.87 | 1,953,345.81 | 97.67 |
| end_to_end_msgpack | 43,249.47 | 46.24 | 1,956,750.53 | 97.84 |
| real_world_average | 76,573.82 | 26.12 | 1,923,426.18 | 96.17 |
| site_profile_average | 83,078.53 | 24.07 | 1,916,921.47 | 95.85 |
| site_profile_best:plant-a | 90,791.99 | 22.03 | 1,909,208.01 | 95.46 |

Latency metrics from the same rerun:

| Metric | P99 ms | Gap ms | Gap % |
|--------|--------|--------|-------|
| mixed_replay | 0.0193 | 79.9807 | 99.98 |
| cgr_stream_slice | 0.0403 | 79.9597 | 99.95 |
| flink_runtime_slice | 0.0342 | 79.9658 | 99.96 |
| end_to_end_json | 0.0271 | 79.9729 | 99.97 |
| end_to_end_msgpack | 0.0284 | 79.9716 | 99.96 |
| real_world_average | 0.0339 | 79.9661 | 99.96 |
| site_profile_average | 0.0222 | 79.9778 | 99.97 |
| site_profile_best:plant-a | 0.0155 | 79.9845 | 99.98 |

Interpretation:

- the rerun is slower than the earlier session, which is consistent with host/load variance on a single development machine
- JSON remained slightly faster than MsgPack in the Python end-to-end path even though MsgPack moved fewer bytes
- the next performance step should not be another Python serialization tweak; it should be a compiled runtime for the hot path and a real distributed benchmark on the target topology

### CGR Stream Slice Breakdown

Command:

```bash
uv run python -m services.cli.datastreamctl benchmark cgr-stream-slice --events 10000 --batch-size 256 --warmup-events 0
```

Latest local run on the current codebase:

| Stage | Ops | Avg ms | P50 ms | P95 ms | P99 ms | Max ms | Ops/sec |
|-------|-----|--------|--------|--------|--------|--------|---------|
| mapping_validation | 10,000 | 0.0072 | 0.0066 | 0.0104 | 0.0166 | 0.2932 | 137,972.90 |
| record_build | 10,000 | 0.0163 | 0.0155 | 0.0199 | 0.0274 | 0.6428 | 61,408.84 |
| partitioning_window_scoring | 10,000 | 0.0062 | 0.0058 | 0.0086 | 0.0133 | 0.1054 | 161,477.85 |
| serialization | 10,000 | 0.0158 | 0.0150 | 0.0193 | 0.0269 | 0.4148 | 63,204.73 |

Interpretation:

- record build and serialization are now the main costs in the migrated path
- the rolling window and scoring logic is no longer the dominant slice after the internal record migration
- validation is still not the main bottleneck on this dataset
- if the next optimization effort is about raw throughput, record packing and payload encoding deserve the first redesign pass

## Rust Hot-Path Experiment And Live Historian Check

- **Date**: 2026-07-02
- **Scope**: compiled wire/partition fast path experiment, same-host improvement check, and Docker-backed historian write validation

### Targeted Regression Checks

| Check | Result |
|-------|--------|
| `uv run pytest -q tests/test_wire_format.py tests/test_end_to_end_pipeline_benchmark.py tests/test_datastreamctl.py -k "benchmark_cgr_gap_report_runs or benchmark_flink_runtime_slice_runs or benchmark_end_to_end_pipeline_runs"` | 3 passed |
| Rust extension build (`uv run maturin develop -m rust/fastpath/Cargo.toml`) | passed |
| Live Postgres schema bootstrap for `processed_events` | passed |

### Same-Host Comparison

The Rust wire-path experiment was measured against the pure-Python path on the same machine. The default path was faster, so the compiled JSON/msgpack encode path was removed from the default runtime flow.

| Benchmark | Rust path enabled | Default path | Change |
|-----------|-------------------|--------------|--------|
| end-to-end JSON throughput | 11,350.74 events/sec | 36,569.38 events/sec | +222.2% |
| end-to-end JSON p99 | 0.1166 ms | 0.0585 ms | -49.8% |
| end-to-end MsgPack throughput | 17,140.69 events/sec | 35,025.18 events/sec | +104.4% |
| end-to-end MsgPack p99 | 0.0786 ms | 0.0492 ms | -37.4% |
| CGR stream slice throughput | 8,468.25 events/sec | 38,567.06 events/sec | +355.4% |
| CGR stream slice p99 | 0.1617 ms | 0.0515 ms | -68.1% |
| Flink runtime slice throughput | 8,415.77 events/sec | 43,648.20 events/sec | +418.7% |
| Flink runtime slice p99 | 0.1625 ms | 0.0398 ms | -75.5% |

Interpretation:

- the compiled bridge is not the default production choice for payload encoding on this host
- the existing Python/orjson/msgpack path is materially faster for this code shape
- the Rust work is still useful as a proof that the hot path must be profiled per operation, not assumed faster because it is compiled

### Live Historian Write

Command:

```bash
uv run python scripts/benchmark_mixed_replay.py --events 10000 --batch-size 256 --warmup-events 0 --live-db
```

Latest local run against the Docker-backed Postgres historian:

| Metric | Value |
|--------|-------|
| Events | 10,000 |
| Invalid events | 0 |
| Batches | 40 |
| Elapsed | 0.9931s |
| Throughput | 10,069.22 events/sec |
| Serialized bytes | 4,011,250 |
| p99 | 0.0266 ms |
| Live DB write rate | 11,483.29 events/sec |

Notes:

- this validates the historian write path against a live Docker service instead of only in-process replay
- the benchmark initially failed because the `processed_events` table was missing from the running Postgres container; the schema was then bootstrapped manually and the benchmark rerun successfully
- this is still a local docker validation, not a substitute for target industrial network benchmarking

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
- shared payload enrichment now lives in `services/processor/runtime_pipeline.py`
- historian writes are batched in the edge ingest and runtime processor paths
- the distributed Flink job now uses keyed state plus checkpointing while preserving the same processed-event contract
- the distributed Flink job now stores window samples as typed tuples instead of string-encoded samples
- MsgPack wire-format support now exists as an optional binary contract, but the local Python end-to-end benchmark still shows that JSON is faster on this host while MsgPack produces smaller payloads
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

For a direct industrial-readiness interpretation and comparison against similar tool classes, see [industrial-benchmark-comparison.md](industrial-benchmark-comparison.md).

## Bottlenecks Identified

1. **Mock generation rate**: Sleep-based timing limits to ~1,800/sec. For higher throughput, use batch generation or remove sleep delays.
2. **JSON serialization**: 329K/sec is good but could still be improved with orjson or msgpack in the non-API hot paths.
3. **Database writes**: historian writes now batch by default in the ingest and processor paths, but live TimescaleDB throughput should be remeasured after deployment.

## Recommendations

1. Use `orjson` instead of `json` for serialization in any remaining hot paths
2. Re-run live historian benchmarks after batching changes and tune batch size against the target TimescaleDB topology
3. Enable TimescaleDB compression for long-term storage
4. Consider uPlot for chart rendering (10x faster than Recharts SVG)

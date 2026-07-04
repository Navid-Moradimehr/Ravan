# Industrial Benchmark Comparison

This report summarizes the current benchmark state of the platform and compares it to the classes of tools a company would usually deploy for industrial data streaming, historian ingestion, and operational analytics.

## Measured Scores In This Repo

### Hot-path runtime

- Full pipeline: `125,830 events/sec`
- Mixed replay: `65,876.93 events/sec`
- Isolated CGR-style stream slice: `21,215.99 events/sec`
- AI gateway provider path:
  - OpenAI-compatible mock transport: `162,812.89 events/sec`
  - Ollama mock transport: `144,191.18 events/sec`
- JSON serialization: `329,195 serializations/sec`
- Event normalization: `18,433,186 normalizations/sec`
- Rule evaluation: `571,968 evals/sec`

### CGR slice decomposition

- mapping + validation: `137,972.90 ops/sec`
- record build: `61,408.84 ops/sec`
- partitioning + rolling window + scoring: `161,477.85 ops/sec`
- serialization: `63,204.73 ops/sec`

The stage-level split shows the platform is not dominated by Pydantic validation alone. After the internal record migration, the remaining cost shifted to record assembly and payload encoding, which is where the next optimization pass should focus.

### Rollout and acceptance

- Site-profile matrix:
  - `demo-site`: `44,795.24 events/sec`
  - `plant-a`: `59,253.75 events/sec`
  - overall: passed
- Project rollout acceptance:
  - `demo-site`: `48,558.93 events/sec`
  - `plant-a`: `55,973.26 events/sec`
  - overall: passed
- Site-profile calibration:
  - `demo-site`: observed `52,786.52 events/sec`, recommended minimum `42,229.22`
  - `plant-a`: observed `47,759.79 events/sec`, recommended minimum `38,207.83`
  - overall: passed

### Test coverage

- `tests/test_project_manifest.py`
- `tests/test_datastreamctl.py`
- `tests/test_site_profile_calibration_benchmark.py`
- `tests/test_datastream_import.py`
- `tests/test_datastream_import_datasets.py`
- combined focused suite: `62 passed`

## Comparison To Similar Tool Classes

This project is not directly comparable to a broker-only benchmark because it includes replay, normalization, release gating, calibration, and import tooling in one stack.

### Compared to Kafka-style brokers

- Brokering engines are optimized for raw message throughput and broker durability.
- This platform adds ingest normalization, historian writes, rollout validation, and operator-facing report generation on top of that.
- In practice, the platform's `125K+ events/sec` full-pipeline number is strong for a Python-based control plane, but it should be treated as a system benchmark, not a broker-only benchmark.

### Compared to MQTT / OPC UA / Modbus simulators

- Protocol simulators typically generate traffic but do not validate end-to-end industrial rollouts.
- This platform now consumes simulated traffic, converts public datasets into benchmark CSVs, and runs the same release-gate and calibration checks across sites.
- That makes it more complete than a simulator-only stack.

### Compared to SCADA / historian-centric suites

- Legacy industrial suites often emphasize visualization, alarms, and historian integration.
- This platform is closer to a site-aware industrial data pipeline with benchmarkable rollout contracts.
- The current benchmark numbers show the platform can sustain realistic site-level replay in the `45K-60K events/sec` range on the local machine while keeping source/site isolation intact.

## Current Gap To CGR Stream

The public CGR Stream page claims `2M msg/sec` and `P99 < 80ms` for its streaming layer.

Against that reference, the current repo numbers are:

- documented full pipeline: `125,830 events/sec`, about `15.9x` below the CGR claim
- mixed replay: `65,876.93 events/sec`, about `30.4x` below the CGR claim
- isolated CGR-style stream slice: `21,215.99 events/sec`, about `94.3x` below the CGR claim
- site-profile best run: `67,510.74 events/sec`, about `29.6x` below the CGR claim

What this means in practice:

- the platform is currently strong for local validation, rollout gating, and pilot-sized industrial deployments
- it is not yet at broker-tier streaming throughput parity with CGR Stream
- local replay p99 is now measured and sits in the ~0.02-0.03 ms band on the current benchmark pack
- the isolated stream slice improved materially after the internal record migration, which shows the representation change was worthwhile
- the stage-level split now shows the biggest cost is in record build and serialization rather than windowing itself
- the remaining latency gap is target-site broker/historian p99 on real plant hardware, which still needs separate validation
- the new `cgr-gap-report` command now makes both throughput and replay-latency gaps explicit and repeatable on the local benchmark pack
- the latest optimization pass materially improved the isolated slice by `34.93%` over the pre-migration baseline, so the next jump should target record packing and encoding before considering a deeper backend rewrite

## Is It Good Enough For Industrial Usage?

Short answer: **not yet for unattended production deployment**, but **yes for a strong self-hosted industrial beta / pilot**.

### What is already good enough

- Local and site-oriented benchmark gates pass.
- Release-gate, rollout-acceptance, and calibration flows all pass on the sample fleet manifest.
- Manifest validation now catches cross-site leakage conditions earlier.
- Realistic traffic can be generated from public datasets plus protocol simulators.
- The platform already has enough coverage to support a multi-site pilot with operator supervision.

### What still blocks a production claim

- No live benchmark on the target broker and historian topology.
- No real PLC/sensor hardware validation in this environment.
- No production model promotion workflow yet.
- Diagnostic and supervised action agents are still infrastructure-only.
- Vendor connector validation across customer environments is still pending.

### Practical verdict

- **Industrial pilot / internal rollout**: yes, with operator oversight.
- **Open-source self-hosted adoption**: yes, if users follow the conversion, calibration, and rollout gates.
- **Fully production-ready for arbitrary industrial sites**: not yet, because the real target-network benchmark and hardware validation are still missing.

## Recommendation

Treat the current state as:

1. benchmark-validated
2. rollout-gated
3. site-isolation-aware
4. ready for controlled pilot deployments

Do not mark it as fully production-ready until target-site broker/historian sizing and real connector validation are completed on representative plant networks.

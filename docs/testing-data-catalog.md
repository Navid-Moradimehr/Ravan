# Testing Data Catalog

## Purpose

This document lists realistic data sources for validating Local Stream Engine.

The catalog is split into:

- built-in mock data
- synthetic research datasets
- industrial benchmark datasets
- cyber-physical security datasets
- operational recommendations for how to use each one inside this platform

## How to think about “real” vs “mock”

### Built-in mock data

Best for:

- smoke testing
- UI validation
- fast regression testing
- deterministic replay

### Synthetic industrial datasets

Best for:

- anomaly detection experiments
- fault classification testing
- controlled scenario evaluation

### Real or near-real industrial datasets

Best for:

- historian validation
- predictive maintenance baselines
- correlation and fault-analysis testing
- proving that the platform generalizes beyond generated data

## Recommended Data Sources

## 1) Built-in Platform Data

### Local mock generator

**Type**

- synthetic

**Good for**

- full pipeline smoke tests
- performance tests
- protocol compatibility checks

**How to use**

- run the built-in generator directly into ingest topics
- use it for fast CI and repeatable demos

### Scenario engine outputs

**Type**

- synthetic but controlled

**Good for**

- testing alarm logic
- validating drift, spike, dropout, stuck, noisy, and degradation behavior
- measuring known-fault versus detected-fault metrics

**How to use**

- combine with built-in replay or mock generation

## 2) AI4I 2020 Predictive Maintenance

**Type**

- synthetic industrial predictive-maintenance dataset

**Signals**

- rotational speed
- torque
- air temperature
- process temperature
- tool wear
- failure labels

**Best use**

- predictive maintenance demos
- scenario evaluation
- classification and severity workflows

**Why it fits this platform**

- already maps well into asset-tag telemetry
- supports fault-labeled replay
- easy starting point for UI and analytics validation

## 3) Industrial Mixed Benchmark Pack

**Type**

- local benchmark replay data

**Location**

- `data/benchmarks/industrial_mixed_benchmark.csv`

**Signals**

- mixed MQTT, OPC UA, and Modbus-style telemetry
- pumps, motors, and turbine tags
- labeled normal, drift, spike, degradation, and reset scenarios

**Best use**

- replay-based load testing
- historian write-path validation
- severity and alert tuning
- multi-protocol benchmark cases

**How to use**

- replay the CSV with `services/datasets/replayer.py`
- stage it with `datastream-import fetch industrial-benchmark --local data/benchmarks/industrial_mixed_benchmark.csv`
- use it for repeatable performance runs when you need a mixed plant-like payload set

**Why it fits this platform**

- exercises the same normalization shape as the real ingest path
- includes multiple protocols and assets in one compact file
- useful for testing batch historian writes and UI behavior under realistic event mixes

## 4) NASA C-MAPSS

**Type**

- simulated engine degradation dataset

**Signals**

- multiple sensor channels
- operating settings
- run-to-failure trajectories

**Best use**

- degradation and remaining-useful-life style experiments
- trend visualization
- long-horizon replay

**Why it fits this platform**

- strong for historian and analytics testing
- useful for slow-degradation scenarios
- good candidate for transfer-learning examples

## 5) IMS / NASA Bearing Run-to-Failure

**Type**

- bearing degradation benchmark

**Signals**

- vibration-focused time-series data
- run-to-failure structure

**Best use**

- vibration analytics
- anomaly detection
- maintenance alerting logic

**Why it fits this platform**

- aligns well with condition-monitoring workflows
- good for asset-tag mapping where one machine has multiple vibration channels

## 6) SKAB

**Type**

- anomaly benchmark based on Skoltech measurements

**Signals**

- industrial telemetry with anomaly labels

**Best use**

- anomaly benchmarking
- comparing rules against model-based detectors
- precision and recall tuning

**Why it fits this platform**

- compact and practical for repeated experiments
- good for evaluating multiple detector strategies quickly

## 7) NAB

**Type**

- anomaly benchmark with real-world time-series examples

**Signals**

- mixed time-series anomalies

**Best use**

- detector benchmarking
- baseline scoring comparisons
- regression testing for anomaly algorithms

**Why it fits this platform**

- good benchmark for analytics quality even if not purely industrial
- useful for algorithm testing before plant-specific fine-tuning

## 8) SWaT

**Type**

- cyber-physical industrial control system dataset

**Signals**

- water treatment process tags
- attack and normal-operation traces

**Best use**

- ICS security analytics
- historian validation on process-style telemetry
- alerting and incident workflows

**Why it fits this platform**

- very strong match for process-industry use cases
- useful for security-aware alarms and multi-tag event analysis

## 9) WADI

**Type**

- water distribution industrial control dataset

**Signals**

- process telemetry and attack scenarios

**Best use**

- cybersecurity testing
- anomaly correlation
- rule plus ML evaluation

**Why it fits this platform**

- complements SWaT
- useful for multi-stage and distributed process patterns

## 10) MIMII

**Type**

- machine-condition dataset using industrial sound recordings

**Signals**

- audio rather than classic sensor telemetry

**Best use**

- future multimodal monitoring
- anomaly classification research

**Why it fits this platform**

- useful later if audio or edge inference becomes part of the roadmap
- not a first-priority integration for the current platform

## Which datasets to prioritize

### Priority 1: already best aligned

- AI4I 2020
- NASA C-MAPSS
- IMS bearing
- SKAB

These are the best immediate fits for:

- replay
- historian validation
- predictive maintenance analytics
- ground-truth evaluation

### Priority 2: security and process operations

- SWaT
- WADI

These are the best next datasets for:

- industrial process tags
- alarm workflows
- security and fault-correlation testing

### Priority 3: algorithm benchmarking

- NAB

Use this mainly to compare detectors rather than to mimic a full plant.

## Recommended platform mapping

### AI4I

- one asset per machine
- map each sensor column to a tag
- use existing replay and scenario controls

### C-MAPSS

- one asset per engine unit
- tags for each sensor and operational setting
- use for slow degradation and trend-heavy testing

### IMS bearing

- one asset per bearing rig
- vibration tags and derived RMS or feature tags
- ideal for alarms and maintenance reset scenarios

### SWaT / WADI

- map plant stages to site/area/line/cell
- map process variables to tags
- use for multi-asset correlation and security-driven alarms

## Mock Data Strategy for Open-Source Users

For the public release, include three testing packs:

### Pack A: quick demo

- tiny built-in synthetic set
- starts instantly
- useful for screenshots and tutorials

### Pack B: industrial analytics

- AI4I + SKAB adapters
- best for anomaly and maintenance demos

### Pack C: advanced validation

- C-MAPSS + IMS + SWaT/WADI adapters
- best for deeper replay and benchmarking

## Suggested next implementation steps

1. standardize dataset manifests in one catalog file
2. add downloader/import commands for public datasets
3. add column-mapping presets per dataset
4. add replay profiles such as `fast`, `real-time`, and `stress`
5. add evaluation reports per dataset run

## Practical Recommendation

If only a few datasets are going to be supported first, start with:

1. AI4I 2020
2. NASA C-MAPSS
3. SKAB
4. SWaT

That gives the platform:

- predictive maintenance coverage
- degradation coverage
- anomaly benchmark coverage
- process-industry security coverage

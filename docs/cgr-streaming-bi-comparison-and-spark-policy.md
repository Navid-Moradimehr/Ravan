# CGR Comparison And Spark Policy

This note captures the current architectural decision point for the open-source release.

## What CGR Publicly Presents

The public CGR streaming page describes a managed industrial streaming stack centered on Kafka/Redpanda, Kafka Connect, Schema Registry, Flink, ksqlDB, MQTT bridging, CDC, MirrorMaker 2, tiered storage, and observability. Their public claim is much closer to a tuned multi-node production service than to a local replay harness.

The public CGR BI page describes an OLAP-oriented analytics stack centered on ClickHouse/Druid with a LookML-style semantic layer, dashboards, SQL exploration, and governed analytics.

## What This Platform Is

This repository is a self-hosted industrial platform with:

- local-first deployment
- open-source runtime and benchmark tooling
- multi-site manifest and rollout support
- Kafka-compatible ingestion
- a Python fallback processor plus a Flink-oriented distributed contract
- historian storage and simulation/replay tooling
- provider-neutral LLM integration for open-weight and OpenAI-compatible backends

That means the platform is not trying to be a copy of the CGR implementation. It is aiming for a compatible industrial operating model that users can deploy inside their own network.

## Why We Should Not Expect Identical Performance

- CGR is a commercial product with a mature distributed runtime, production cluster sizing, and managed operational tuning.
- Our current local benchmark suite still includes Python and in-process replay paths.
- The repo is optimized for portability, extensibility, and self-hosting rather than a single closed benchmark topology.
- Raw throughput depends heavily on broker partitions, serialization format, storage backend, checkpointing, and hardware layout.

## How We Close The Gap

The right path is to improve the same kinds of bottlenecks CGR is likely tuning:

- keep Flink on the distributed hot path
- remove avoidable JSON/list parsing in keyed state
- use a typed internal event contract
- add a real end-to-end Kafka/Flink/historian benchmark
- tune broker partitions, batching, compression, and checkpointing
- separate real-time streaming from BI/OLAP workloads
- keep MsgPack or another binary wire contract optional until the benchmark proves it beats JSON on the target host
- consider a compiled hot path if Python object handling remains the dominant cost after serialization tuning

## Spark Policy

Apache Spark should be treated as an optional integration layer, not a required core dependency.

Use Spark for:

- heavy backfills
- lakehouse ETL
- feature generation
- batch reporting
- long-range historical joins
- ML training and offline analytics

Do not use Spark as the default hot path for PLC/sensor streaming if the goal is low-latency stateful processing. Flink is the better fit for that path.

The platform should therefore expose:

- stable Kafka topics and schemas
- lake/export sinks
- optional Spark job templates
- optional BI materialization guidance

Users who already operate Spark can plug it in themselves without forcing every installation to carry a Spark runtime.

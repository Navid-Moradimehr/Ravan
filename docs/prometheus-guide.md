# Prometheus Guide

Prometheus is the metrics backend for the platform. It does not show the business workflow of the system and it does not store historian records. Its job is narrower and more technical: collect time-series metrics from the services, keep them queryable, and make it possible to answer questions like “is the ingest path healthy?”, “is the AI gateway slow?”, or “are the services still scraping correctly?”

In this platform, Prometheus is the source of the live observability data that the Command Center and the Observability page summarize. Grafana reads from it for dashboards. The UI cards on the platform read from the observability API, which in turn queries Prometheus for the latest values and uses fallback snapshots if Prometheus is unavailable.

## What Prometheus is for

Use Prometheus when you need the raw monitoring truth behind the visuals. Grafana is good for charts. The platform observability page is good for operator-friendly summaries. Prometheus is what you use when you want to query the actual metric series, inspect the scrape targets, or understand why a chart has the values it does.

Typical questions Prometheus helps answer:

- Is Kafka being scraped?
- Is the AI gateway exposing latency metrics?
- Is the edge ingest path generating throughput metrics?
- Are the expected services still online as scrape targets?
- Is a metric present at all, or is the chart showing fallback data?

## What users should look at first

When a user opens Prometheus, the first useful things to inspect are targets, query results, and metric names. Targets tell you whether a service is being scraped. Queries tell you whether the metric exists and whether it is changing. Metric names tell you which layer of the platform is producing the signal.

For this repository the important metric families are the ones behind ingest throughput, AI latency, historian health, and delivery lag. Those are the signals that the platform turns into operator-facing cards and dashboards.

## How to use it

If you are trying to understand a healthy system, start by checking whether the metrics source is up and whether the expected targets are being scraped. Then query a small number of metrics directly. If you are trying to debug a problem, compare the live metric values in Prometheus with the values shown in Grafana or the Observability page. That tells you whether the issue is in the source service, the scrape layer, or the visualization layer.

If a chart looks wrong, do not start by editing the dashboard. Start by querying the underlying metric in Prometheus. If the metric is missing, the problem is in the emitting service. If the metric exists but the chart is wrong, the issue is in the query, aggregation, or dashboard config.

## How it fits the platform

Prometheus is part of the monitoring plane, not the business data plane. It helps validate that the platform is working, but it does not own the industrial events themselves. Those events still flow through Kafka, the processor, and the historian. Prometheus only tracks the health of those flows and the services that support them.

The default Compose deployment runs Flink as the processing owner, so the
optional Python fallback processor is not registered as a scrape target. This
prevents a deliberate, stopped fallback container from appearing as a runtime
failure. If an operator explicitly runs the Python fallback profile, its
metrics should be inspected through its configured endpoint or a deployment-
specific Prometheus configuration.

## Why it matters for operators

Operators use Prometheus when they need to confirm that a signal is live before trusting a dashboard. Engineers use it when they need to understand the source of a number. Platform maintainers use it when they are verifying rollout health, latency, or ingest behavior during a deployment.

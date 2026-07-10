# Processing Walkthrough

The Processing page is the runtime surface for the middle of the pipeline. It sits after ingestion and before the historian. If the Pipeline page answers “did the record get in?”, the Processing page answers “what happened to it while it was being scored, enriched, and handed off?”

This page is more operational than the Pipeline page and more runtime-focused than the Observability page. It shows how the platform behaves when it is using the host Python fallback or the distributed Flink path, and it keeps the visible contract the same across both.

## What the page shows

The page has four parts:

1. Runtime summary cards
2. Processing runtime section
3. Shared observability panels
4. Runtime notes in the right rail

## 1) Runtime summary cards

These cards summarize the current processing contract.

What they do:

- show whether the runtime is starting, active, or degraded
- show the batch path from `iot.raw` to `iot.processed`
- show the handoff from processed events into AI enrichment
- show the state model used for streaming windows and keyed state

Inputs:

- live telemetry from the runtime stream
- fallback state if telemetry has not arrived yet

Outputs:

- visible runtime summary at the top of the page

How users use it:

- operators can see whether the processing layer is healthy
- engineers can confirm which path is active
- maintainers can tell whether they are looking at live state or fallback state

## 2) Processing runtime section

This section explains the runtime envelope.

What it does:

- compares the Python fallback, local Flink, and production Flink envelopes
- keeps the same normalization and scoring contract across all of them
- explains that the implementation strategy changes, but the platform meaning stays the same

What each mode means:

- `Python fallback` is the simplest local path for development and benchmark harnesses
- `Flink local` is the distributed stateful runtime for plant-local or site-local deployments
- `Flink production` is the checkpointed keyed-processing path for larger or multi-site setups

Inputs:

- the current runtime configuration
- the current deployment mode

Outputs:

- a clear explanation of which runtime envelope is active

How users use it:

- a developer uses Python fallback when debugging logic
- a site operator uses Flink local when validating production-style behavior on one server or one site
- a larger deployment uses Flink production when it needs checkpointed streaming state and better scaling

## 3) Shared observability panels

This section is where Processing and Observability overlap on purpose.

What it does:

- shows throughput, latency, protocol mix, severity mix, and service health
- gives the processing page a small amount of live telemetry context
- reuses the same observability component used on the dedicated Observability page

Why it is here:

- processing needs to show whether runtime changes are affecting throughput or latency
- the shared component prevents duplication of chart code
- the page still stays centered on runtime behavior instead of becoming a full monitoring dashboard

Inputs:

- observability snapshot from Prometheus-backed data
- fallback snapshot when metrics are unavailable

Outputs:

- compact health and runtime telemetry panels

How users use it:

- check whether processing changes are increasing latency
- compare runtime mode with throughput and AI handoff behavior
- confirm that the processing layer still matches the expected runtime contract

## 4) Runtime notes

The right rail explains how to think about the page.

What it does:

- reminds the user that Python is for debugging and Flink is for distributed behavior
- shows the currently active runtime mode

Why it matters:

- it keeps the page practical for both development and deployment validation
- it prevents confusion between runtime choice and business logic

## How the page fits the platform

Processing sits in the middle of the platform. It is the place where raw events become scored, enriched, and ready for historian storage or AI consumption. It does not own source protocol setup, and it does not own long-term storage. It owns the runtime contract that transforms normalized streams into processed outputs.

## Typical user flow

1. Open the Processing page.
2. Check the runtime summary cards.
3. Read the runtime envelope section to see whether Python or Flink is active.
4. Inspect the observability panels to make sure latency and throughput still look healthy.
5. Read the right-rail note to understand how the current runtime should be used.

## Processing vs Observability

These pages are related, but not the same.

- Processing is about the runtime path and how events are transformed.
- Observability is about the metrics that tell you whether the whole stack is healthy.

Processing includes a small observability slice because runtime changes should be visible immediately. Observability is still the authoritative place to inspect metrics, latency, DLQ totals, and service health.


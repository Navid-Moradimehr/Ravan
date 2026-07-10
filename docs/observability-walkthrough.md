# Observability Walkthrough

The Observability page is the monitoring surface for the platform. It is where users go when they want to know whether the stack is healthy, how fast it is moving, and where the pressure is building. It is not the ingest page, not the historian page, and not the runtime-processing page. Its job is to turn platform metrics into something operators can read quickly.

## What the page shows

The page has four parts:

1. Summary cards
2. Live observability alerting state
3. Observability panels
4. Signal sources in the right rail

## 1) Summary cards

These cards give the fastest answer to “is the platform healthy?”

What they do:

- show ingest throughput
- show AI latency
- show DLQ total
- show Prometheus state

Inputs:

- Prometheus-backed observability data
- fallback snapshot when live metrics are unavailable

Outputs:

- small operational summary cards at the top of the page

How users use it:

- operators check whether the ingest path is active
- engineers check whether AI latency has drifted
- maintainers use DLQ totals to see whether the pipeline is rejecting data

## 2) Live observability alerting state

This section only appears when the page is using a fallback snapshot.

What it does:

- warns the user that one or more observability sources were unavailable
- explains that the page is still usable even if live metrics were not reachable

Why it matters:

- it prevents operators from confusing fallback data with live data
- it makes the monitoring contract honest about source availability

## 3) Observability panels

This is the main monitoring body of the page.

What it does:

- shows throughput trends
- shows AI latency trend data
- shows protocol mix
- shows severity mix
- shows service health over time

Inputs:

- Prometheus queries
- AI gateway metrics
- edge ingest metrics
- historian and DLQ signals

Outputs:

- charts and signal panels

How users use it:

- compare throughput over time
- inspect whether a protocol is dominant or missing
- compare AI latency across the observed window
- look for severity spikes and DLQ pressure

## 4) Signal sources

The right rail explains where the page gets its signals.

What it does:

- tells the user that Prometheus, AI gateway telemetry, edge metrics, and historian state all contribute
- makes the page feel like a combined health surface rather than a single-service dashboard

How users use it:

- they can trace a chart back to the kinds of services that feed it
- they can see that this page is about the whole runtime, not one subsystem

## How it fits the platform

Observability sits beside the historian and pipeline pages, but it has a different job. The Pipeline page now carries the runtime processing summary as part of the combined route. Observability is about whether the runtime is healthy. Historian is about what happened and how to query it later. Those three areas are related, but they are not the same thing.

## Typical user flow

1. Open Observability.
2. Check the summary cards.
3. Look for the fallback warning if live metrics are unavailable.
4. Read the charts for throughput, latency, protocol mix, and severity mix.
5. Use the right rail to understand which signal sources feed the page.

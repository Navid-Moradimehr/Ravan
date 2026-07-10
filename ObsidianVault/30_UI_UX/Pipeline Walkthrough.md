# Pipeline Walkthrough

The Pipeline page is the pre-storage boundary of the platform. It is where the user sees the flow from industrial source systems into the platform before data is written to the historian or used in analytics. This page is intentionally narrower than the Command Center: it focuses on extraction, validation, normalization, routing, and the preview of what the stream looks like after those steps.

## What the page shows

The page has four parts:

1. Ingress lanes
2. Pipeline stages
3. Event preview
4. Boundary notes in the right rail

The page is mostly a simulated or contract-oriented view today. The endpoints and labels are real platform concepts, but the visible source endpoints on the page are illustrative so users can understand the shape of the pipeline without needing live hardware attached.

## 1) Ingress lanes

This section describes the protocol adapters.

What it does:

- shows the protocol families the platform supports at the edge
- gives a quick view of whether each protocol lane is active
- provides a rough rate and latency label for each source

What it represents:

- OPC UA
- MQTT
- Modbus TCP

How to read it:

- `OPC UA` usually represents structured industrial data from PLCs and controllers
- `MQTT` usually represents sensor or gateway-published data
- `Modbus TCP` usually represents register-based industrial polling

Inputs:

- edge protocol payloads
- simulator endpoints in the local development stack

Outputs:

- raw ingress events that move toward validation and normalization

How users use it:

- operators verify that each protocol lane is alive
- engineers check whether one source is missing, slow, or degraded
- users learn which industrial protocol should be connected to which edge device

## 2) Pipeline stages

This section shows the transformation path.

What it does:

- shows the platform’s high-level path from extraction to routing
- explains what happens before durable storage
- separates the validation and normalization boundary from the downstream lanes

Stage meaning:

- `Extract` is where source data enters from OPC UA, MQTT, or Modbus
- `Validate` is where schema and quality checks happen
- `Normalize` is where raw data becomes the canonical industrial stream
- `Route` is where good records continue and bad records move to the DLQ

Inputs:

- protocol payloads from the ingress lanes
- schema and quality rules

Outputs:

- `industrial.raw`
- `industrial.normalized`
- `industrial.dlq`
- compatibility lanes such as `iot.raw`

How users use it:

- users can understand the platform without reading code
- operators can explain where a record was accepted, transformed, or rejected
- maintainers can use it to reason about where to add new checks or sinks

## 3) Event preview

This section shows representative records after extraction and normalization.

What it does:

- displays sample asset, tag, value, protocol, and quality rows
- shows the shape of the data after it has been interpreted by the pipeline
- helps users understand what the canonical event stream looks like

Inputs:

- preview records from the current pipeline model

Outputs:

- a table that demonstrates the event format the platform expects

How users use it:

- a first-time user can see how sensor or PLC data is represented
- an integrator can compare their data with the platform’s event contract
- a developer can quickly confirm that the preview shape matches the intended ingestion model

## 4) Boundary notes

The right rail explains the scope of the page.

What it does:

- reminds the user that this route is about pre-storage flow
- clarifies that the page is meant for source isolation, normalization, and DLQ behavior

Why that matters:

- it prevents confusion between ingestion and historian behavior
- it keeps the pipeline page from becoming a general dashboard
- it makes the page useful as a troubleshooting surface

## How the page fits the overall platform

The Pipeline page sits before the historian and before the main analytics surfaces. It answers questions like “did the data get in?”, “did it pass validation?”, and “what did the normalized record look like?” It does not answer long-term storage questions or deep BI questions. Those belong to the historian and observability surfaces.

## Typical user flow

1. Open the Pipeline page.
2. Check the ingress lanes to see whether the protocol source is active.
3. Read the stage cards to understand where the record is in the flow.
4. Inspect the event preview to confirm the shape of the data.
5. Use the boundary notes to understand what this page is responsible for and what happens elsewhere.


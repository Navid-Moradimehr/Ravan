# Site Observability

The platform now exposes a logical site-observability snapshot.

## Purpose

This is a rollout-facing contract that answers a simple question:

Is the site healthy enough to trust?

It surfaces:

- broker health
- historian health
- AI gateway health
- backup readiness
- API health
- SLO targets for the deployment mode

## What It Is Not

This is not a replacement for Prometheus, Grafana, or the metrics stack.

The continuous signals still belong in the monitoring system. This snapshot is
for operators, rollout gates, and release validation.

## Current Implementation

- `services/common/site_observability.py`
- `services/api_service/routers/observability.py`
- `/api/v1/observability/site`


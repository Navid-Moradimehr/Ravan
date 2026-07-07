# Operational Memory

The platform now exposes a logical operational memory surface.

## Purpose

Operational memory is the operator-facing layer for state that is not historian telemetry and not semantic structure:

- alerts and incidents
- operator annotations
- shifts and OEE context
- report templates and generated reports
- backup and restore readiness

This layer is read-only in the current release. It is meant to stabilize the contract now so later workflow features can plug into it without changing the platform core.
The underlying alert, collaboration, and report-template stores can also be made file-backed with opt-in local state paths, so the snapshot can survive restarts in single-node deployments without turning operational memory into a workflow system. Report schedules are rehydrated from the persisted template store when the schedule library is available, so recurring exports do not vanish after restart.

## What It Is Not

Operational memory is not a full MES replacement.

It does not own:

- production orders
- work orders
- approvals
- maintenance planning
- recipe execution

Those remain user-owned until a later phase.

## Current Implementation

- `services/common/operational_memory.py`
- `services/api_service/routers/operational_memory.py`
- `/api/v1/metadata/operational`

The snapshot reuses existing alert, annotation, OEE, report, and backup surfaces.
Those surfaces now have optional file-backed durability hooks for local installs, but the operational-memory API remains a read-only projection over them.

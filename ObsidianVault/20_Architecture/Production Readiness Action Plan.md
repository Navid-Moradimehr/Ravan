# Production Readiness Action Plan

**Date**: 2026-07-04

This note turns the readiness gap report into a checklist with owners and exit criteria.

## Agent And Runtime

- Diagnostic-agent runtime
  - Owner: Platform / Modeling
  - Exit: read-only runtime contract, enforced tool policy, audit trail
- Supervised action-agent runtime
  - Owner: Platform / Governance
  - Exit: approval workflow and audit trail, but no autonomous execution
- Audited tool execution logs
  - Owner: Platform / Security
  - Exit: all agent-assisted tool calls land in audit storage

## Deployment And Rollout

- Multi-node Kubernetes pilot
  - Owner: DevOps / Platform
  - Exit: single-node deployment works on a local cluster and scales to a multi-node test cluster
- Restore and rollback drills
  - Owner: Ops / QA
  - Exit: measured restore and rollback timings for at least two site profiles
  - Ownership: each site profile should declare who owns scheduled backups and who owns restore drills
- Vendor device validation
  - Owner: Edge / QA
  - Exit: real or near-real PLC/sensor traffic exercises the connectors

## Production Maturity

- Model evaluation lifecycle
  - Owner: Modeling / QA
  - Exit: evaluate, promote, and roll back models predictably
- Observability and SLOs
  - Owner: Platform / Ops
  - Exit: sustained lag, restore, and runtime metrics are defined and measured
- Per-site benchmark baselines
  - Owner: QA / Ops
  - Exit: repeatable benchmark baselines exist for each site profile

## Release Rule

- Treat the platform as pilot-ready now.
- Treat enterprise-scale production readiness as blocked on real multi-node and real-device validation.
# Local Hardening Completed

The platform now includes a deterministic local resilience campaign and a
deployment preflight. The resilience campaign exercises malformed, duplicate,
out-of-order, outage, spool, and replay cases without requiring real PLCs or
Kafka. The preflight composes existing site-profile, project-manifest, compose,
and soak-scenario validators. Contract tests verify context preservation from
canonical event validation through normalization and runtime enrichment.

These checks improve release confidence but do not prove site-specific driver,
network, storage, or failover behavior.

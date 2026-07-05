# Production Readiness Action Plan

**Date**: 2026-07-04

This is the executable version of the readiness gap report. Each item has an owner, the exit criterion that must be met, and the current status.

## A. Agent And Runtime Gaps

| Item | Owner | Exit criterion | Status |
|------|-------|----------------|--------|
| Diagnostic-agent runtime | Platform / Modeling | Read-only diagnostic runtime contract exists, tool registry is enforced, audit logging works, and no write-capable action is exposed by default | In progress |
| Supervised action-agent runtime | Platform / Governance | Action request contract, approval workflow, and audit trail exist; no autonomous action execution is shipped | In progress |
| Audited tool execution logs | Platform / Security | Every agent-assisted tool invocation is logged to the historian audit table with actor, site, tool, and arguments | In progress |
| Policy layer for tool access | Platform / Security | Allowed tools are computed from the role and site profile, and write-capable tools are blocked in the diagnostic runtime | In progress |
| Sandboxed integration boundary | Platform / Runtime | User-provided orchestration can call the exposed runtime contract without modifying core services | In progress |

## B. Deployment And Rollout Gaps

| Item | Owner | Exit criterion | Status |
|------|-------|----------------|--------|
| Multi-node Kubernetes pilot | DevOps / Platform | Single-node deployment is proven on a local cluster and the same release starts cleanly on a multi-node test cluster | Pending |
| Target-site broker/historian validation | Ops / QA | Benchmarks and soak tests run on the actual broker and historian topology used in rollout | Pending |
| Restore and rollback drills | Ops / QA | At least two site profiles have measured restore and rollback drills with recorded RTO/RPO | In progress |
| Vendor device validation | Edge / QA | MQTT, OPC UA, Modbus, and representative PLC/sensor devices are tested with real traffic | Pending |
| Compatibility matrix expansion | Edge / Platform | Additional PLC/sensor families are covered and documented | Pending |

## C. Production-Maturity Gaps

| Item | Owner | Exit criterion | Status |
|------|-------|----------------|--------|
| Model evaluation lifecycle | Modeling / QA | Model evaluation, promotion, and rollback contracts exist | Pending |
| Observability and SLOs | Platform / Ops | Sustained lag, restore, and agent runtime SLOs are defined and measured | Pending |
| Per-site benchmark baselines | QA / Ops | Each site profile has a repeatable benchmark baseline and variance window | In progress |
| Packaging and installer maturity | Release / Ops | Signed release artifacts and install docs are complete enough for standard rollout | In progress |

## D. Release Exit Criteria

The platform can be called production-ready for pilot release when all of the following are true:

1. Diagnostic runtime infrastructure is stable and read-only by default.
2. Action-runtime scaffolding exists but no autonomous actions ship enabled.
3. Multi-node cluster validation passes on a single-machine local Kubernetes setup.
4. Site-local and federated profiles pass restore and rollback drills.
5. Real or representative vendor device traffic validates the connector layer.
6. Per-site benchmarks are repeatable within the documented variance window.
7. The release notes clearly separate pilot-ready scope from enterprise-scale claims.

## E. Ownership Model

- Platform: runtime contracts, model registry, semantic plane, read-only agent infrastructure
- Security: audit trails, permissions, policy enforcement
- Ops: deployment, backups, restore drills, SLO measurement
- QA: benchmarks, compatibility matrix, regression gates
- Release: packaging, installer docs, signed artifacts

## F. Recommended Execution Order

1. Validate the diagnostic runtime and audit logging path end to end.
2. Keep supervised action runtime as scaffolding only.
3. Run the same release on a local single-node Kubernetes cluster.
4. Measure restore/rollback and benchmark variance on two site profiles.
5. Expand vendor/device validation using real or near-real traffic.

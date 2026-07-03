# Production Hardening Checklist

Date: 2026-07-03

This checklist turns the current roadmap into a concrete execution track for a self-hosted industrial release.

## 1. Multi-Site Rollout

- [x] Keep site-local broker, historian, AI gateway, and ingest defaults.
- [x] Keep `site_id`, source identity, and source protocol explicit in the project manifest.
- [x] Validate topic ownership and site boundary coverage.
- [x] Validate that each manifest site profile exists.
- [ ] Validate that each site profile `site.id` matches the manifest `site_id` for every rollout bundle.
- [ ] Add per-site rollout acceptance reports for at least two independent site profiles.
- [ ] Measure restore and rollback drills per site before federation is enabled.
- [ ] Keep cross-site replication limited to approved rollups, summaries, or explicit bridges.

## 2. Self-Hosted Security

- [x] Keep mutating API requests protected by bearer-token middleware by default.
- [x] Keep auth and RBAC as local/self-hosted infrastructure rather than cloud-managed dependencies.
- [x] Keep secrets out of exported manifests.
- [x] Keep TLS support available for MQTT, OPC UA, and Modbus TCP.
- [ ] Enforce deployment guidance for operator-managed secret stores.
- [ ] Document the minimum trusted network zones for broker, historian, and model endpoints.
- [ ] Add a release note that default JWT placeholders are not production-safe.
- [ ] Add a clear secret-injection reference for Docker, systemd, and Kubernetes.

## 3. Packaging and Distribution

- [x] Keep packaging work separate from core runtime refactoring.
- [x] Keep generated bundles available for flat, systemd, Kubernetes, and packaged site layouts.
- [ ] Publish installable release artifacts with versioned runtime bundles.
- [ ] Add signed release outputs for operators who need verification.
- [ ] Provide one-click-ish install guidance without hiding configuration ownership.

## 4. Real-World Simulator and Benchmarks

- [x] Keep a mixed replay benchmark pack in the repo.
- [x] Keep site-profile soak and calibration scripts available.
- [x] Keep CGR gap reporting available for local comparisons.
- [ ] Add explicit scenario definitions for multi-PLC line traffic, burst traffic, dropout, and reconnect behavior.
- [ ] Add repeat-run guidance so benchmark sessions are compared by median and variance, not one sample.
- [ ] Keep simulator output close to protocol-shaped industrial traffic.
- [ ] Separate architecture validation from target-hardware sizing claims.

## 5. Immediate Next Implementation Targets

1. Finish the manifest/site identity validation gap.
2. Add site-profile and project-manifest regression tests.
3. Update the Obsidian vault with the execution state.
4. Keep packaging on the back burner until the runtime shape is settled.


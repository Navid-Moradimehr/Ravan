# Production Hardening Checklist

Date: 2026-07-03

This checklist turns the current roadmap into a concrete execution track for a self-hosted industrial release.

## 1. Multi-Site Rollout

- [x] Keep site-local broker, historian, AI gateway, and ingest defaults.
- [x] Keep `site_id`, source identity, and source protocol explicit in the project manifest.
- [x] Validate topic ownership and site boundary coverage.
- [x] Validate that each manifest site profile exists.
- [x] Validate that each site profile `site.id` matches the manifest `site_id` for every rollout bundle.
- [x] Add per-site rollout acceptance reports for at least two independent site profiles.
- [ ] Measure restore and rollback drills per site before federation is enabled.
- [ ] Keep cross-site replication limited to approved rollups, summaries, or explicit bridges.

## 2. Self-Hosted Security

- [x] Keep mutating API requests protected by bearer-token middleware by default.
- [x] Keep auth and RBAC as local/self-hosted infrastructure rather than cloud-managed dependencies.
- [x] Keep secrets out of exported manifests.
- [x] Keep TLS support available for MQTT, OPC UA, and Modbus TCP.
- [x] Enforce deployment guidance for operator-managed secret stores.
- [x] Document the minimum trusted network zones for broker, historian, and model endpoints.
- [x] Add a release note that default JWT placeholders are not production-safe.
- [x] Add a clear secret-injection reference for Docker, systemd, and Kubernetes.

## 3. Packaging and Distribution

- [x] Keep packaging work separate from core runtime refactoring.
- [x] Keep generated bundles available for flat, systemd, Kubernetes, and packaged site layouts.
- [x] Publish release-artifact skeletons with versioned runtime bundles.
- [ ] Add signed release outputs for operators who need verification.
- [ ] Provide one-click-ish install guidance without hiding configuration ownership.

## 4. Real-World Simulator and Benchmarks

- [x] Keep a mixed replay benchmark pack in the repo.
- [x] Keep site-profile soak and calibration scripts available.
- [x] Keep CGR gap reporting available for local comparisons.
- [x] Add explicit scenario definitions for multi-PLC line traffic, burst traffic, dropout, and reconnect behavior.
- [x] Add repeat-run matrix reporting so benchmark sessions are compared by median and variance, not one sample.
- [x] Keep simulator output close to protocol-shaped industrial traffic.
- [ ] Separate architecture validation from target-hardware sizing claims.

## 5. Immediate Next Implementation Targets

1. Measure restore and rollback drills on at least two site profiles.
2. Add signed release outputs for the release-package skeleton.
3. Validate the rollout and benchmark baseline on target hardware.
4. Keep the release-package skeleton separate from the eventual signed installer pipeline.

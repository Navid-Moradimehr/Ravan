# Production Readiness Gap Report

**Date**: 2026-07-04

## Summary

- The semantic plane is now production-grade for the current single-node and site-local release shape.
- Benchmark fixtures now reflect industrial-shaped traffic and multi-site correlation.
- The distributed path is explicit in the site profile contract, but still needs real multi-node pilot validation.

## Done

- semantic DB backing with file fallback
- retrieval/modeling context integration
- industrial benchmark fixture hardening
- multi-site correlation simulator case
- explicit `SEMANTIC_STORE_BACKEND=db` for plant-local and federated profiles
- backup-drill matrix tooling for per-site restore/rollback measurement
- AI4I and C-MAPSS public dataset import and benchmark conversion
- SWaT workbook/CSV normalization path with benchmark coverage on a synthetic workbook fixture
- SWaT first-class simulator case

## Still Missing

- real target-site broker/historian validation
- multi-node Kubernetes pilot runs
- restore/rollback drills on multiple site profiles
- real PLC/sensor vendor compatibility validation
- model evaluation/promotion lifecycle
- diagnostic and supervised action agents
- one more SWaT verification pass against the exact upstream workbook source used in public distribution

## Release Stance

- safe for pilot and controlled production use on a single site or site-local fleet
- not yet safe to claim as fully enterprise-validated across multiple sites and vendors
- remaining work is primarily real-world deployment validation

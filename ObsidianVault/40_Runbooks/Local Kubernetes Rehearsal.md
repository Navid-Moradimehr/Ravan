# Local Kubernetes Rehearsal

The repository now includes a disposable `kind` rehearsal path for the
platform's Kubernetes contract.

## What it gives us

- a repeatable single-node local cluster
- validation of generated Kubernetes bundles
- optional Flink Kubernetes Operator install
- optional application of the platform FlinkDeployment

## Why it matters

This fills the gap between Docker Compose and a real cluster without claiming
multi-node production readiness. It is enough to check that the repo's
manifests, image references, and operator flow are coherent on one machine.

## Key boundary

- platform-owned: manifest generation, capacity contract, operator guidance
- user-owned: cluster, operator repo, registry image, storage, network policy

# Deployment Decision Memo

## Decision

Ship the platform as a native, self-hosted industrial runtime first.

The default release shape should be:

- `datastreamd` as the installed runtime service
- `datastreamctl` as the operator and automation CLI
- the existing local web UI as the main visual surface
- optional Docker-compose support for demos and lab environments

## Why this is the right default

Industrial users usually install these systems on:

- Windows Server
- Linux Server
- industrial PCs
- edge gateways
- virtualization hosts
- sometimes Kubernetes nodes for large sites

That is the same deployment pattern used by major industrial tools: service-first, console-assisted, locally managed, and able to run without a cloud dependency.

## WSL2 recommendation

Use WSL2 only for:

- developer workstations
- quick local demos
- compatibility testing on Windows laptops

Do not make WSL2 a required production dependency.

Reasons:

- it is a developer convenience, not a plant runtime standard
- it adds an extra OS layer that most production operators do not want to support
- it complicates service management, monitoring, and recovery
- it is unnecessary because the platform can run natively on Windows and Linux

If the target machine is a workstation used for development, WSL2 can be offered as an optional helper path. If the target is a real plant host, install natively.

## What should be included in the installation package

Include:

- the runtime service binaries or Python runtime bundle
- `datastreamctl`
- default config templates
- site profile templates
- manifest templates
- local benchmark and diagnostic commands
- backup and restore helpers
- service registration files for Windows and Linux
- uninstall and rollback scripts
- checksum and signature verification files
- sample replay data and smoke-test datasets
- offline dependency bundle for air-gapped sites
- documented upgrade path

Optionally include:

- Docker Compose files for lab/demo environments
- a local UI launcher
- test-only sample models or mock endpoints

## What should not be bundled

Do not bundle:

- cloud credentials
- customer API keys
- production TLS private keys
- PLC passwords
- historian passwords
- real model weights that are licensed or site-owned
- WSL2 itself as a required component
- Docker Desktop as a hard requirement

Those are operator-owned or environment-owned dependencies.

## OS support recommendation

Priority 1:

- Ubuntu Server
- Debian
- Windows Server

Priority 2:

- RHEL / Rocky / Alma
- Windows 10/11 for developer and demo installs

Priority 3:

- ARM64 edge devices
- Kubernetes-based multi-site installations

## Device support recommendation

The platform should expect to run on:

- industrial PCs
- SCADA/gateway servers
- edge boxes
- virtual machines
- rack servers in a plant network

It should not expect to run directly on PLCs.

## Packaging guidance

The install package should:

1. verify prerequisites
2. place files in a stable site root
3. register a service
4. run a health check
5. run a backup drill
6. record host profile and benchmark baselines

That gives operators a repeatable installation that can be audited and rolled back.

## Recommendation summary

- Native install first
- WSL2 optional for dev only
- Linux and Windows Server first
- packaged runtime plus CLI plus UI
- operator-owned secrets and network placement
- offline-friendly and air-gapped compatible

This is the safest and most supportable path for an industrial open-source release.

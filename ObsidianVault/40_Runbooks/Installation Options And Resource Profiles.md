# Installation Options And Resource Profiles

## Product Packages

- Linux Site Server: complete single-site runtime.
- Linux Edge Collector: protocol collection and store-and-forward near devices.
- Windows Full Node: complete runtime through a managed Linux appliance.
- Windows Operator: desktop client for a local or remote runtime.
- macOS Operator: desktop client for a local or remote runtime.
- Kubernetes Helm bundle: multi-node and multi-site deployment.
- Docker Compose: development and laboratory deployment.

## Resource Tiers

The platform itself does not require a GPU. A GPU is only needed when users
choose local model inference. Cloud, LM Studio, Ollama, vLLM or another remote
model service can be used without adding a platform GPU.

### Edge

2 CPU cores, 4 GB RAM, and storage sized for the desired store-and-forward
window.

### Core Site Without AI/Lakehouse

4 CPU cores and 8 GB RAM is a small-site baseline; 16 GB RAM is recommended.
Use at least 100 GB SSD, excluding long-term retention.

### Sustained Production Site

8 CPU cores and 16 to 32 GB RAM is a practical starting profile. Separate fast
storage for Kafka and TimescaleDB is useful at higher rates.

### AI And Lakehouse

Remote models add network and gateway capacity, not GPU requirements. Local
models and large training datasets must be sized independently by model size,
concurrency, retention and training workload.

## Ownership Boundary

Platform-owned: event contracts, validation, normalization, Kafka, Flink,
historian interface, replay, metadata, diagnostics and benchmark gates.

User-owned: endpoints, certificates, credentials, asset semantics, retention,
backups, identity, external storage, model endpoints and GPU sizing.

Related: [[Data Integrity Contract]], [[Source Connection And Deployment]],
[[Flink Operator Runbook]], [[Lakehouse And External S3]].

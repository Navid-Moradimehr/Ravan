# Deployment Payload Boundaries

This document defines what belongs in an installed Ravan deployment, what belongs in the public GitHub repository, and what is development-only. It is based on the current repository layout and the existing staging script in `scripts/package-release.py`.

The goal is to ship a usable self-hosted platform with the demo site and demo data available, without shipping private working notes, the Obsidian vault, test suites, benchmark campaigns, local machine state, or generated build output.

## 1. Installer and Runtime Payload

These files are required by an installer or a deployed runtime. The exact subset depends on the deployment mode, but the categories below are the runtime contract.

### Application code

- `services/`: API, ingestion, processing, fan-out, historian, AI gateway, CLI, metadata, and runtime modules.
- `ui/`: production Next.js application source and its lockfile. A native installer should ship the built UI artifact rather than the development cache or source-only test helpers.
- `rust/fastpath/`: optional native fast path source or its compiled artifact when that runtime is enabled.
- `pyproject.toml`, `requirements.txt`, and `uv.lock`: Python dependency and CLI installation metadata.
- `README.md`, `README_API.md`, and `README_DATA.md`: public orientation and API/data contract references.

### Runtime configuration and deployment definitions

- `config/`: project manifest, site profiles, assets, source templates, policies, and connector configuration examples.
- `docker/docker-compose.yml`: Compose deployment definition for the complete local stack.
- `docker/Dockerfile*`, `docker/flink-job-entrypoint.sh`, and service-specific Docker configuration.
- `docker/kafka/`, `docker/postgres/`, `docker/prometheus/`, and `docker/grafana/`: broker, historian, metrics, dashboards, migrations, and provisioning.
- `k8s/`: Helm chart and Flink Operator manifests for Kubernetes installations. These are deployment inputs, not required for a native single-host installer.
- `.env.example`: safe configuration template. Never ship a populated `.env` containing user or developer secrets.

### Demo and sample data

- `data/`: demo datasets and sample benchmark input that are explicitly licensed for redistribution.
- `config/site-profiles/` and demo asset/configuration files: the demo site definition used by the first-run experience.
- Simulator entry points required for the demo mode, only when the selected installation mode supports them.

The installed package should make demo mode discoverable and runnable, but should keep demo traffic opt-in. It must not silently treat demo credentials, retention, or open local endpoints as production security settings.

### User guidance shipped with an installer

Ship a curated subset of `docs/`, not the entire working documentation history:

- `docs/self-host-install-guide.md`
- `docs/installation-options-and-requirements.md`
- `docs/source-connection-walkthrough.md`
- `docs/source-connection-and-deployment.md`
- `docs/first-time-plc-ingest-guide.md`
- `docs/industrial-edge-pipeline.md`
- `docs/historian-guide.md`
- `docs/observability-walkthrough.md`
- `docs/kafka-ui-guide.md`
- `docs/prometheus-guide.md`
- `docs/grafana-source-charts-workflow.md`
- `docs/ai-provider-configuration.md`
- `docs/ai-reporting-policy-and-jobs.md`
- `docs/lakehouse-and-s3-guide.md`
- `docs/self-hosted-secrets.md`
- `docs/runtime-lifecycle.md`
- `docs/update-and-release-operations.md`
- `docs/user-facing-source-and-ai-reporting.md`

The UI help and guidance page should link to the same curated user-facing material. Installer documentation must explain that credentials, TLS, identity, retention, external storage, and plant-specific mappings remain customer-owned.

## 2. Public Open-Source GitHub Repository

The repository should contain the source needed to build, inspect, extend, and self-host the platform:

- `services/`, `ui/`, `rust/`, `docker/`, `k8s/`, `config/`, and `scripts/` source needed to reproduce supported deployments.
- `data/` demo data and deterministic simulators that are safe to redistribute.
- `docs/` curated user guidance, architecture contracts, API references, compatibility notes, and selected validation evidence.
- `tests/` unit, contract, integration, and simulator tests. These should remain in GitHub for maintainers and contributors even though they are excluded from installer payloads.
- `README.md`, `README_API.md`, `README_DATA.md`, `pyproject.toml`, `requirements.txt`, `uv.lock`, `ui/package.json`, and `ui/package-lock.json`.
- `.env.example`, licensing files, contribution guidance, issue templates, and CI configuration when present.

The public repository should not include credentials, populated environment files, local Docker volumes, generated archives, build caches, or the private Obsidian vault.

## 3. Development-Only Material

The following must not be copied into an installer and should generally remain outside a public release unless a maintainer intentionally extracts a sanitized public artifact:

- `ObsidianVault/`: private second-brain notes, working decisions, implementation history, and internal links.
- `.git/`, `.refs/`, `.datastream/`, `backups/`, `reports/`, `build/`, `dist/`, `.pytest_cache/`, `__pycache__/`, `*.egg-info/`, `ui/.next/`, `ui/node_modules/`, and Rust `target/` output.
- `.env` and any credential, certificate, private-key, token, or local endpoint files.
- `tests/` and test-only fixtures in installers. Keep them in the GitHub repository for maintainers.
- `scripts/*benchmark*`, `scripts/*soak*`, protocol failure-matrix scripts, Playwright smoke tests, and one-off migration/research scripts in installers. Keep them in GitHub or a separate validation bundle.
- Historical implementation logs, internal comparison notes, raw benchmark artifacts, screenshots, and exploratory research notes unless converted into a concise user-facing release note.
- `comparission.md`, `AI/`, and other unclassified working files until each item has been reviewed for licensing, secrets, and public usefulness.

Development-only does not mean unimportant. These materials remain valuable for maintainers, release qualification, and incident investigation; they simply do not belong in a customer runtime payload.

## Current Staging Script Assessment

`scripts/package-release.py` currently copies `services`, `config`, `scripts`, `ui`, and `rust`, plus a small set of root files. Offline mode also copies `data` and selected installation documents. This is useful staging logic, but it is not yet a final installer allowlist:

- Windows and Linux modes currently omit `data`, so they do not consistently provide the demo site/data promised by this document.
- Copying the whole `scripts/` directory risks shipping benchmarks, soak tests, and development utilities.
- Copying the whole `ui/` directory risks shipping `playwright-smoke.cjs`, source-only development material, and unnecessary frontend files unless the installer intentionally supports source-based UI startup.
- The runtime payload needs an explicit curated documentation list and a package manifest that records whether demo data and simulators are present.
- `ObsidianVault/`, tests, generated output, local state, and secrets must remain excluded by explicit allowlists, not only by convention.

## Recommended Packaging Contract

Use an allowlist per deployment mode:

1. Native Windows/Linux: runtime services, production UI artifact, config templates, demo data, required service definitions, and curated user docs.
2. Docker Compose: Compose files, Dockerfiles, service configuration, demo data, curated user docs, and the images or image-build inputs required by the release.
3. Kubernetes: Helm chart, Flink Operator contract, configuration templates, image references or an offline image bundle, demo data where appropriate, and curated runbooks.
4. GitHub source release: all maintainable source, tests, simulator/benchmark tools, architecture docs, and contributor material, excluding secrets and private vault content.

Every package should include a machine-readable manifest stating the version, deployment mode, included demo assets, required operator inputs, image digests where applicable, and excluded development material. Packaging changes should be validated by inspecting the archive contents before publication.

## Demo First-Run Behavior

The demo site should be present in the installed version but remain isolated from a customer's real site configuration:

- Use a clearly named `demo-site` profile and deterministic mock sources.
- Keep demo sources disabled or opt-in unless the selected product mode is explicitly `demo`.
- Keep demo data in its own topic namespace, historian scope, and retention policy where feasible.
- Show users how to replace the demo profile with their own site profile and source credentials.
- Never reuse demo credentials or public endpoints for production connections.

This boundary lets a new user see the full ingestion, Kafka, Flink, historian, observability, and AI flow without implying that the demo configuration is production-safe.

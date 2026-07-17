# Deployment Payload Boundaries

The public deployment boundary is documented in [[Deployment Payload Boundaries]].

## Decision

- Installer payloads include runtime code, deployment definitions, safe config templates, demo assets, and curated user guidance.
- GitHub includes maintainable source, tests, simulators, benchmarks, architecture contracts, and contributor documentation.
- Installers exclude tests, private working notes, `ObsidianVault`, secrets, generated output, local state, and benchmark/soak tooling.

## Important Packaging Gap

The current `scripts/package-release.py` is a staging implementation, not the final installer allowlist. Windows/Linux modes do not consistently copy demo data, and whole-directory copies can include development-only scripts. Before packaging begins, convert it to explicit per-mode allowlists and verify archive contents.

## Demo Contract

The installed product must retain an opt-in `demo-site` with deterministic mock sources so users can observe the full platform flow without PLC access. Demo data and topics must remain clearly separated from customer site configuration.

# Ravan Operator Shell

This directory contains the desktop operator shell for Windows and macOS.
It is intentionally not a local Kafka, Flink, TimescaleDB, or Python runtime.
The shell asks for the URL of a running Ravan Site Server and opens that URL
inside a native dedicated window. It does not install or manage the runtime.

## Prerequisites

- Node.js 20+ and npm for the frontend tooling.
- Rust 1.77.2+ and the platform-specific Tauri prerequisites for packaging.
- A running Ravan Site Server, normally the Linux Docker Engine Compose bundle.

## Development

```bash
npm install
npm run tauri dev
```

The shell loads its local launcher screen first. Enter a Site Server URL such
as `http://localhost:3006` and select **Open Ravan**. Authentication,
authorization, TLS, and network access remain the customer's Site Server
configuration; the shell does not bypass or replace them.

## Build targets

```bash
npm run build:windows       # Windows runner: NSIS and MSI
npm run build:macos         # macOS runner: DMG
```

The repository also provides `scripts/build-operator-installer.ps1` for
Windows and `scripts/build-operator-installer.sh` for macOS/Linux runners.
They use the committed npm lockfile and copy generated bundles into
`dist/operator-installer`.

The release workflow builds unsigned Windows NSIS/MSI and macOS DMG artifacts.
The native bundle uses a numeric prerelease version (for example `1.0.0-1`)
because MSI does not accept the platform's human-readable `beta.1` prerelease
label. The release workflow derives this safe native version from the Git tag.
Code signing, notarization, update channels, icons, and clean-machine
acceptance require maintainer-owned release credentials and remain explicit
release work. The operator shell is still only a client for a Site Server; it
does not install Kafka, Flink, TimescaleDB, or connectors.

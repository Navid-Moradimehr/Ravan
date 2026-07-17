# Ravan Operator Shell

This directory is the desktop operator shell scaffold for Windows and macOS.
It is intentionally not a local Kafka, Flink, TimescaleDB, or Python runtime.
The shell asks for the URL of a running Ravan Site Server and opens that URL
inside a native window.

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
npm run tauri build
```

The Tauri configuration declares Windows and macOS bundles. Code signing,
notarization, update channels, icons, and clean-machine acceptance are release
pipeline work and are intentionally not claimed by this scaffold.

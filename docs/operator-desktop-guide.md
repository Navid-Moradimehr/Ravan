# Ravan Desktop Workflow

Ravan uses a two-part installation on Windows and macOS:

1. Docker Desktop runs the complete Ravan Site Server.
2. Ravan Operator opens that Site Server in a dedicated application window.

The Operator is not a second platform. It is a small desktop client for the
same dashboard that users can open in a browser. Kafka, Flink, TimescaleDB,
source connectors, Grafana, Prometheus, and the AI gateway remain in the Site
Server runtime.

## Windows or macOS

1. Install Docker Desktop and start it.
2. Download and start the Ravan Compose package.
3. Wait until the Site Server health checks are ready.
4. Install the Ravan Operator application.
5. Open Ravan Operator.
6. Enter `http://localhost:3006` for a local Site Server, or enter the address
   of a remote Site Server.
7. Select **Open Ravan**.

Ravan opens in its own application window. Users do not need to keep a normal
browser tab open for the main Ravan interface. The Operator remembers the last
Site Server address locally, but it does not store platform passwords, API
keys, or customer secrets.

### Windows local Site Server shortcut

Windows users who want the complete local runtime can use the repository's
managed Compose bootstrap after installing Docker Desktop:

```powershell
.\scripts\ravan-windows-site.ps1 -Action start
.\scripts\ravan-windows-site.ps1 -Action status
.\scripts\ravan-windows-site.ps1 -Action open
```

This is a convenience launcher, not a native replacement for Docker Desktop.
It starts the complete Site Server through Compose and leaves source endpoints,
credentials, ports, storage, and security under operator control. The Windows
Operator remains the dedicated application window for the running Site Server.

## Remote Site Server

The Operator can connect to a Site Server on another Linux server or Kubernetes
cluster. The user enters the approved HTTPS address instead of
`http://localhost:3006`. Network access, TLS, authentication, authorization,
and reverse-proxy configuration remain controlled by the company.

## What remains separate

Grafana, Kafka UI, Prometheus, and Flink's web interface are operator links to
supporting tools. They may open in a browser or separate tool window depending
on the operating system. They are not duplicated inside the Ravan runtime.

## Linux

Linux industrial servers should normally run the Linux Site Server installer
as a background systemd service. Users may access it through a browser or a
future Linux desktop Operator. The server does not need a desktop session.

## macOS boundary

The macOS package is an Operator client. It is intentionally not presented as
an industrial Site Server because the production runtime needs Kafka, Flink,
the historian, connectors, and persistent storage to run on a Linux server or
an approved Kubernetes environment. A macOS user can use Docker Desktop for
local evaluation, or connect the Operator to a remote Site Server.

## Runtime ownership

The Site Server owns the industrial data pipeline. The Operator only provides
the desktop entry point. Closing the Operator does not stop ingestion,
processing, storage, or alarms on the Site Server.

Maintainers can run the `CI` workflow with **Run workflow** and provide an
optional operator version to build a DMG on a native macOS runner without
publishing a release. The result is an unsigned validation artifact until Apple
Developer signing and notarization credentials are added. The standalone
`Ravan Operator macOS Validation` workflow is retained as a release-maintainer
reference, but the active CI workflow is the supported dispatch path.

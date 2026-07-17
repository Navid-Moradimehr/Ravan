# Linux Site Server Install

The Linux Site Server package is Ravan's first complete installer path. It
runs the full single-site platform with Docker Engine and Docker Compose: the
Kafka backbone, Flink runtime, TimescaleDB historian, API, dashboard, edge
ingestion, Prometheus, Grafana, and the supporting services selected by the
Compose profiles.

This is a host installer, not a native replacement for Docker. The operator
must install and maintain Docker Engine, the Compose v2 plugin, the host
firewall, storage, backups, device-network access, TLS, and the company's
authentication boundary. Ravan does not put secrets in the package.

## Install From A Release Archive

1. Install Docker Engine and the Docker Compose v2 plugin on a supported Linux
   server. Confirm both commands work as the same operator account that will
   run the installation:

   ```bash
   docker version
   docker compose version
   ```

2. Extract the `demo-site-site-server.zip` archive. The extraction directory
   must contain `runtime/`, `site/`, and `install/linux/install.sh`.

3. Install the local source-build variant for a lab or a disconnected build
   host:

   ```bash
   sudo install/linux/install.sh --mode source-build
   ```

   This builds Ravan application images from the source tree inside the
   archive. It still downloads third-party images or Python/Docker build
   dependencies unless those images and build inputs are already cached.

4. Install the registry variant when the release images have been published
   to, or mirrored into, the company's registry:

   ```bash
   sudo install/linux/install.sh \
     --mode registry \
     --version 1.0.0-beta.1 \
     --image-registry ghcr.io/navid-moradimehr
   ```

   The current installer accepts registry settings through environment
   variables. For an internal registry, use:

   ```bash
   sudo RAVAN_IMAGE_REGISTRY=registry.example.internal/ravan \
     RAVAN_VERSION=1.0.0 \
     install/linux/install.sh --mode registry
   ```

5. The installer creates `/opt/ravan` and a systemd unit named
   `ravan-site.service`. It copies the generated site configuration, creates a
   mutable `/opt/ravan/.env`, and starts the service unless `--no-start` is
   supplied.

6. Replace development values in `/opt/ravan/.env` before accepting plant
   traffic. In particular set database passwords, object-storage credentials,
   model endpoints or API keys, allowed browser origins, ports, retention, and
   any site-specific connector configuration. The generated site file is
   metadata and defaults; it is not a secret store.

## Operate And Verify

Use systemd for lifecycle operations:

```bash
sudo systemctl status ravan-site
sudo systemctl restart ravan-site
sudo journalctl -u ravan-site -f
```

Ravan also installs a small operator wrapper:

```bash
sudo /opt/ravan/bin/ravan-site status
sudo /opt/ravan/bin/ravan-site doctor
sudo /opt/ravan/bin/ravan-site logs 200
```

The doctor validates Docker Compose configuration, systemd state, running
containers, the API health endpoint, and the dashboard endpoint. A failed
doctor result is an operational signal, not proof that a PLC or external
model endpoint is reachable; those endpoints remain site-owned settings.

The default local URLs are:

- Dashboard: `http://server-address:3006`
- API health: `http://server-address:8020/health`
- Kafka UI: `http://server-address:18080`
- Grafana: `http://server-address:13000`
- Prometheus: `http://server-address:19090`

Expose these ports only through the operator's network and authentication
boundary. Do not expose them directly to an untrusted network.

## Configuration And Data Ownership

The installer replaces the runtime code and Compose definitions on a later
upgrade, but does not overwrite an existing `/opt/ravan/.env`. Docker named
volumes remain outside the install directory and are not removed by service
stop, reinstall, or ordinary uninstall. Back up the volumes and `/opt/ravan`
before upgrades.

The platform owns canonical events, Kafka contracts, deterministic processing,
replay, historian schemas, metadata contracts, and the operator health tools.
The site operator owns real PLC/sensor addresses, credentials, certificates,
network routes, retention, backups, external S3 or MinIO settings, model
providers, and AuthN/AuthZ.

## Uninstall And Upgrade

The normal uninstall is data-preserving:

```bash
sudo /opt/ravan/bin/ravan-site uninstall
```

It stops and disables the systemd service, removes the unit, stops the Compose
containers, and preserves `/opt/ravan` plus Docker named volumes. A destructive
directory purge requires an explicit confirmation:

```bash
sudo /opt/ravan/bin/ravan-site uninstall --purge --yes
```

Named Docker volumes are still not removed by this command. Remove them only
after a verified backup and a deliberate site-retirement decision.

For an upgrade, install the new archive over the same target with `--force`.
The installer keeps the existing `.env` and named volumes, validates the new
Compose definition, rebuilds or pulls the selected images, and restarts the
systemd service. Run the doctor and a backup drill after the upgrade.

## Current Boundary

This installer is functional on Linux systems with Docker Engine, Compose v2,
and systemd. It is not executed by the Windows development workstation because
Windows does not provide systemd. A clean Linux host, WSL2 distribution with
systemd enabled, or Linux VM must be used for final installation acceptance.
Windows and macOS one-click applications remain the lightweight Ravan Operator
shell; they connect to a Site Server and do not replace this runtime.

#!/usr/bin/env python3
"""Render the image-based Compose file used by a Linux Site Server release."""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml


SERVICE_IMAGE_ROLES = {
    "ai-gateway": "ai-gateway",
    "processor": "processor",
    "fanout": "processor",
    "processed-fanout": "processor",
    "ai-fanout": "processor",
    "mqtt-sim": "edge",
    "opcua-sim": "edge",
    "modbus-sim": "edge",
    "edge-ingest": "edge",
    "dashboard": "dashboard",
    "jobmanager": "flink-runtime",
    "taskmanager": "flink-runtime",
    "flink-job": "flink-job",
    "operational-fanout": "processor",
    "artifact-fanout": "processor",
    "dataset-worker": "processor",
    "raw-lakehouse-archive": "processor",
    "api-service": "api",
}


def render_release_compose(source: Path, destination: Path) -> Path:
    """Convert source-build services into registry-backed release services."""
    document = yaml.safe_load(source.read_text(encoding="utf-8"))
    services = document.get("services", {})
    for service_name, role in SERVICE_IMAGE_ROLES.items():
        service = services.get(service_name)
        if not isinstance(service, dict):
            continue
        service.pop("build", None)
        service["image"] = (
            "${RAVAN_IMAGE_REGISTRY:-ghcr.io/navid-moradimehr}/"
            f"ravan-{role}:${{RAVAN_VERSION:-1.0.0-beta.1}}"
        )
        volumes = service.get("volumes")
        if isinstance(volumes, list):
            service["volumes"] = [
                volume for volume in volumes
                if not (isinstance(volume, str) and volume.startswith("../services/"))
            ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        yaml.safe_dump(document, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return destination


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    render_release_compose(args.source, args.destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

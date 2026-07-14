from pathlib import Path


def test_edge_compose_uses_shared_connection_registry_path():
    compose = Path("docker/docker-compose.yml").read_text(encoding="utf-8")
    edge_start = compose.index("  edge-ingest:")
    edge_lines = compose[edge_start:].splitlines()
    edge_block = "\n".join([edge_lines[0]] + [line for line in edge_lines[1:] if not (line.startswith("  ") and not line.startswith("    ") and line.strip())])
    assert "DATASTREAM_CONNECTION_REGISTRY_PATH: /data/connection-registry.json" in edge_block


def test_edge_supervisor_reconciles_versions_without_new_service():
    source = Path("services/edge_ingest/main.py").read_text(encoding="utf-8")
    assert "config_version" in source
    assert "build_connector_tasks(settings, publisher, stop_event)" in source
    assert "reconcile_connectors" in source

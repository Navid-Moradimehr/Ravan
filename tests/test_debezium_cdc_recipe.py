from __future__ import annotations

import json
from pathlib import Path

import pytest

try:
    import yaml
except ImportError:  # pragma: no cover
    yaml = None

REPO = Path(__file__).resolve().parents[1]
CONNECTOR_PATH = REPO / "docker" / "debezium" / "pg-orders-source.json"
REGISTER_PATH = REPO / "docker" / "debezium" / "register-connectors.sh"
INIT_SQL_PATH = REPO / "docker" / "postgres" / "init.sql"
COMPOSE_PATH = REPO / "docker" / "docker-compose.yml"

pytestmark = pytest.mark.skipif(yaml is None, reason="pyyaml not installed")


def test_connector_config_is_valid_json():
    cfg = json.loads(CONNECTOR_PATH.read_text(encoding="utf-8"))
    assert cfg["name"] == "pg-orders-source"
    config = cfg["config"]
    assert config["connector.class"].endswith("PostgresConnector")
    assert config["plugin.name"] == "pgoutput"
    assert config["slot.name"] == "debezium_orders"
    assert config["publication.name"] == "dbz_orders"
    assert config["table.include.list"] == "public.orders"


def test_connector_uses_incremental_snapshot():
    cfg = json.loads(CONNECTOR_PATH.read_text(encoding="utf-8"))
    config = cfg["config"]
    assert config["snapshot.mode"] == "initial"
    assert config["incremental.snapshot.mode"] == "incremental"


def test_connector_unwraps_envelope():
    cfg = json.loads(CONNECTOR_PATH.read_text(encoding="utf-8"))
    config = cfg["config"]
    assert "unwrap" in config["transforms"]
    assert config["transforms.unwrap.type"].endswith("ExtractNewRecordState")
    assert config["transforms.unwrap.drop.tombstones"] == "true"


def test_register_script_references_config_dir():
    text = REGISTER_PATH.read_text(encoding="utf-8")
    assert "for cfg in" in text
    assert "connectors" in text
    # The script must POST the JSON config files found in its directory.
    assert ".json" in text


def test_init_sql_creates_publication_and_replica_identity():
    sql = INIT_SQL_PATH.read_text(encoding="utf-8")
    # wal_level=logical is on the postgres service command, not in init.sql.
    assert "REPLICA IDENTITY FULL" in sql, "orders table must use replica identity full"
    assert "dbz_orders" in sql, "publication for debezium must be created"
    assert "CREATE PUBLICATION" in sql


def test_postgres_service_uses_logical_wal():
    """wal_level=logical is the CDC prerequisite; it must be on the service."""
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    pg = compose["services"]["postgres"]
    cmd = " ".join(pg.get("command", []))
    assert "wal_level=logical" in cmd, "postgres must run with wal_level=logical for CDC"


def test_connect_service_is_debezium():
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    connect = compose["services"]["connect"]
    assert "debezium/connect" in connect["image"]

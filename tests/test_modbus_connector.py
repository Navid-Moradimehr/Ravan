from __future__ import annotations

from pathlib import Path


def test_modbus_connector_uses_tls_client_only_when_tls_is_configured():
    source = (Path(__file__).resolve().parents[1] / "services" / "edge_ingest" / "connectors" / "modbus.py").read_text(encoding="utf-8")
    assert "ModbusTlsClient(host, port=port, sslctx=sslctx)" in source
    assert "ModbusTcpClient(host, port=port)" in source
    assert "ModbusTcpClient(\n            host,\n            port=port,\n            sslctx=sslctx" not in source

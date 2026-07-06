from __future__ import annotations

import sys
import types

import pytest


@pytest.fixture(autouse=True)
def _stub_psycopg2(monkeypatch):
    psycopg_fake = types.ModuleType("psycopg2")
    psycopg_fake.OperationalError = type("Op", (Exception,), {})
    psycopg_fake.InterfaceError = type("Iface", (Exception,), {})
    psycopg_fake.Error = type("Err", (Exception,), {})
    extras_fake = types.ModuleType("psycopg2.extras")
    extras_fake.Json = lambda o: o
    extras_fake.RealDictCursor = type("RDC", (), {})
    extras_fake.execute_values = lambda *a, **k: None
    pool_fake = types.ModuleType("psycopg2.pool")
    pool_fake.ThreadedConnectionPool = type("TCP", (), {"__init__": lambda *a, **k: None})
    psycopg_fake.extras = extras_fake
    psycopg_fake.pool = pool_fake
    monkeypatch.setitem(sys.modules, "psycopg2", psycopg_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.extras", extras_fake)
    monkeypatch.setitem(sys.modules, "psycopg2.pool", pool_fake)


def test_probe_kafka_true_on_open_socket(monkeypatch):
    """probe_kafka returns True when a TCP connection succeeds."""
    import socket

    from services.api_service import health_probes

    class _FakeSocket:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

    monkeypatch.setattr(socket, "create_connection", lambda addr, timeout=None: _FakeSocket())
    monkeypatch.setenv("KAFKA_BROKERS", "broker:9092")
    assert health_probes.probe_kafka() is True


def test_probe_kafka_false_on_failure(monkeypatch):
    """probe_kafka returns False (never raises) when the connection fails."""
    import socket

    from services.api_service import health_probes

    def boom(addr, timeout=None):
        raise OSError("connection refused")

    monkeypatch.setattr(socket, "create_connection", boom)
    monkeypatch.setenv("KAFKA_BROKERS", "broker:9092")
    assert health_probes.probe_kafka() is False


def test_probe_historian_true_on_select_one(monkeypatch):
    """probe_historian returns True when SELECT 1 succeeds."""
    from services.api_service import health_probes
    from services.historian import client as historian_client

    class _Cur:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def execute(self, q):
            pass

        def fetchone(self):
            return (1,)

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return None

        def cursor(self):
            return _Cur()

    monkeypatch.setattr(historian_client, "get_connection", lambda: _Conn())
    assert health_probes.probe_historian() is True


def test_probe_historian_false_on_failure(monkeypatch):
    """probe_historian returns False (never raises) on DB error."""
    from services.api_service import health_probes
    from services.historian import client as historian_client

    def boom():
        raise RuntimeError("db down")

    monkeypatch.setattr(historian_client, "get_connection", boom)
    assert health_probes.probe_historian() is False


def test_probe_ai_gateway_true_on_2xx(monkeypatch):
    """probe_ai_gateway returns True when the gateway responds < 500."""
    from services.api_service import health_probes

    class _Resp:
        status_code = 200

    monkeypatch.setattr("httpx.get", lambda url, timeout=None: _Resp())
    assert health_probes.probe_ai_gateway() is True


def test_probe_ai_gateway_false_on_5xx(monkeypatch):
    """probe_ai_gateway returns False when the gateway responds >= 500."""
    from services.api_service import health_probes

    class _Resp:
        status_code = 503

    monkeypatch.setattr("httpx.get", lambda url, timeout=None: _Resp())
    assert health_probes.probe_ai_gateway() is False


def test_probe_ai_gateway_false_on_connection_error(monkeypatch):
    """probe_ai_gateway returns False (never raises) on connection error."""
    from services.api_service import health_probes

    def boom(url, timeout=None):
        raise OSError("refused")

    monkeypatch.setattr("httpx.get", boom)
    assert health_probes.probe_ai_gateway() is False

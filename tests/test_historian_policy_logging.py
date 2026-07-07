from __future__ import annotations

import contextlib
import logging

import pytest


class _ExpectedPolicyError(Exception):
    pass


class _FakeCursor:
    def __init__(self):
        self.statements: list[str] = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql: str) -> None:
        self.statements.append(sql)
        if "add_compression_policy" in sql or "add_retention_policy" in sql:
            raise _ExpectedPolicyError("policy already exists")


class _FakeConn:
    def __init__(self):
        self.cursor_obj = _FakeCursor()
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True


def test_setup_retention_policies_suppresses_expected_policy_noise(monkeypatch, caplog):
    from services.historian import client

    fake_conn = _FakeConn()

    @contextlib.contextmanager
    def fake_get_connection():
        yield fake_conn

    monkeypatch.setattr(client, "get_connection", fake_get_connection)
    monkeypatch.setattr(client.psycopg2, "Error", _ExpectedPolicyError)
    caplog.set_level(logging.WARNING)

    client.setup_retention_policies()

    assert fake_conn.committed is True
    assert fake_conn.rolled_back is True
    assert not [record for record in caplog.records if record.levelno >= logging.WARNING]
    assert len(fake_conn.cursor_obj.statements) == 9
    assert "ALTER TABLE industrial_events SET" in fake_conn.cursor_obj.statements[0]

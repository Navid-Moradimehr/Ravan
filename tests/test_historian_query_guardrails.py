from __future__ import annotations

import pytest

from services.historian.client import query_recent_events
from services.common.sql_compiler import validate_readonly_sql


def test_validate_readonly_sql_accepts_selects():
    result = validate_readonly_sql("SELECT * FROM industrial_events LIMIT 10")
    assert result.allowed


def test_validate_readonly_sql_rejects_writes():
    result = validate_readonly_sql("INSERT INTO industrial_events VALUES (1)")
    assert not result.allowed
    assert result.reason is not None


def test_query_recent_events_rejects_unknown_table():
    with pytest.raises(ValueError):
        query_recent_events("not_a_table", 10)

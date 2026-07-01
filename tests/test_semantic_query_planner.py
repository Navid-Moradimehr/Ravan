from __future__ import annotations

from services.common.query_plan import build_query_plan
from services.common.semantic_model import load_semantic_model
from services.common.sql_compiler import compile_readonly_sql, validate_readonly_sql


def test_build_and_compile_alarm_plan():
    model = load_semantic_model()
    plan = build_query_plan("show critical alarms for the last 6 hours", model=model, limit=50)

    assert plan.entity == "processed_events"
    assert plan.measure is None
    assert any(item.field == "severity" for item in plan.filters)

    compiled = compile_readonly_sql(plan, model=model)
    assert compiled.entity == "processed_events"
    assert "FROM processed_events" in compiled.sql
    assert "WHERE" in compiled.sql
    assert "LIMIT %s" in compiled.sql
    assert compiled.params[0] == 6
    assert validate_readonly_sql(compiled.sql).allowed


def test_build_and_compile_count_plan():
    model = load_semantic_model()
    plan = build_query_plan("count events by asset in the last 24 hours", model=model, limit=10)
    compiled = compile_readonly_sql(plan, model=model)

    assert "COUNT(*) AS count" in compiled.sql
    assert "GROUP BY" in compiled.sql or plan.group_by == ()
    assert compiled.params[0] == 24


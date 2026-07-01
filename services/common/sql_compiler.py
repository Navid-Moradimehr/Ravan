from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from services.common.query_plan import CompiledQuery, QueryPlan, compile_query_plan
from services.common.semantic_model import SemanticModel


@dataclass(frozen=True)
class SQLSafetyResult:
    allowed: bool
    reason: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_DISALLOWED_KEYWORDS = {
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "grant",
    "revoke",
    "create",
    "call",
    "copy",
    "do",
    "vacuum",
}


def validate_readonly_sql(sql: str) -> SQLSafetyResult:
    candidate = " ".join(sql.strip().split())
    lowered = candidate.lower()
    if not lowered:
        return SQLSafetyResult(False, "empty sql")
    if ";" in candidate.rstrip(";"):
        return SQLSafetyResult(False, "multiple statements are not allowed")
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return SQLSafetyResult(False, "only select statements are allowed")
    for keyword in _DISALLOWED_KEYWORDS:
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return SQLSafetyResult(False, f"disallowed keyword: {keyword}")
    return SQLSafetyResult(True, warnings=("read-only sql validated",))


def compile_readonly_sql(plan: QueryPlan, *, model: SemanticModel | None = None) -> CompiledQuery:
    compiled = compile_query_plan(plan, model=model)
    safety = validate_readonly_sql(compiled.sql)
    if not safety.allowed:
        raise ValueError(safety.reason or "readonly validation failed")
    return compiled

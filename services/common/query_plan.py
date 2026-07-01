from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
from typing import Any

from services.common.semantic_model import SemanticEntity, SemanticModel, load_semantic_model


_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


@dataclass(frozen=True)
class QueryFilter:
    field: str
    operator: str
    value: Any

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryOrder:
    field: str
    direction: str = "desc"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QueryPlan:
    intent: str
    entity: str
    table: str
    measure: str | None = None
    select_fields: tuple[str, ...] = field(default_factory=tuple)
    filters: tuple[QueryFilter, ...] = field(default_factory=tuple)
    group_by: tuple[str, ...] = field(default_factory=tuple)
    order_by: tuple[QueryOrder, ...] = field(default_factory=tuple)
    limit: int = 100
    time_window: dict[str, Any] | None = None
    search_terms: tuple[str, ...] = field(default_factory=tuple)
    notes: tuple[str, ...] = field(default_factory=tuple)
    source: str = "deterministic"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["filters"] = [item.to_dict() for item in self.filters]
        data["order_by"] = [item.to_dict() for item in self.order_by]
        return data


@dataclass(frozen=True)
class CompiledQuery:
    sql: str
    params: tuple[Any, ...]
    entity: str
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _detect_time_window(tokens: list[str]) -> tuple[dict[str, Any] | None, list[str]]:
    joined = " ".join(tokens)
    notes: list[str] = []
    match = re.search(r"(last|past|previous)\s+(\d+)\s+(minute|minutes|hour|hours|day|days|week|weeks)", joined)
    if match:
        count = int(match.group(2))
        unit = match.group(3)
        notes.append(f"time window detected: {count} {unit}")
        return {"kind": "relative", "count": count, "unit": unit}, notes
    if "today" in tokens:
        return {"kind": "relative", "count": 1, "unit": "day", "anchor": "today"}, ["time window detected: today"]
    if "this" in tokens and "week" in tokens:
        return {"kind": "relative", "count": 1, "unit": "week", "anchor": "this_week"}, ["time window detected: this week"]
    return None, notes


def _pick_entity(model: SemanticModel, tokens: list[str]) -> SemanticEntity:
    lowered = set(tokens)
    if {"alarm", "alarms", "warning", "warnings", "critical", "anomaly"} & lowered:
        entity = model.find_entity("processed_events")
        if entity:
            return entity
    if {"trend", "history", "hist", "telemetry", "events", "measurements"} & lowered:
        entity = model.find_entity("industrial_events")
        if entity:
            return entity
    if {"asset", "assets", "equipment", "hierarchy"} & lowered:
        entity = model.find_entity("assets")
        if entity:
            return entity
    if {"report", "reports", "template", "templates"} & lowered:
        entity = model.find_entity("report_templates")
        if entity:
            return entity
    if {"scenario", "scenarios", "benchmark", "benchmarks"} & lowered:
        entity = model.find_entity("scenarios")
        if entity:
            return entity
    return model.infer_entity(tokens)


def _pick_measure(tokens: list[str]) -> tuple[str | None, list[str]]:
    lowered = set(tokens)
    if {"count", "counts", "how", "many", "number"} & lowered:
        return "count", ["count aggregate requested"]
    if {"average", "avg", "mean"} & lowered:
        return "avg", ["average aggregate requested"]
    if {"max", "maximum", "highest", "peak"} & lowered:
        return "max", ["maximum aggregate requested"]
    if {"min", "minimum", "lowest"} & lowered:
        return "min", ["minimum aggregate requested"]
    if {"sum", "total"} & lowered:
        return "sum", ["sum aggregate requested"]
    if "latest" in lowered or "newest" in lowered or ("most" in lowered and "recent" in lowered):
        return "latest", ["latest record requested"]
    return None, []


def _pick_group_by(entity: SemanticEntity, tokens: list[str]) -> tuple[str, ...]:
    candidates = []
    token_set = set(tokens)
    for field in entity.fields:
        if field.kind != "dimension":
            continue
        alias_terms = {field.name.lower(), *{alias.lower() for alias in field.aliases}}
        if token_set & alias_terms:
            candidates.append(field.name)
    return tuple(dict.fromkeys(candidates))


def build_query_plan(
    query: str,
    *,
    model: SemanticModel | None = None,
    limit: int | None = None,
) -> QueryPlan:
    semantic_model = model or load_semantic_model()
    tokens = _tokenize(query)
    entity = _pick_entity(semantic_model, tokens)
    measure, measure_notes = _pick_measure(tokens)
    time_window, time_notes = _detect_time_window(tokens)
    group_by = _pick_group_by(entity, tokens)

    select_fields: list[str] = []
    if measure == "count":
        select_fields.append("count")
    elif measure in {"avg", "max", "min", "sum"}:
        select_fields.append(measure)
    elif measure == "latest":
        select_fields.append("latest")

    if not select_fields:
        select_fields.append("time" if entity.time_field else entity.fields[0].name if entity.fields else "*")
        for field in entity.fields:
            if field.kind == "dimension" and field.name not in select_fields:
                select_fields.append(field.name)
            if len(select_fields) >= 6:
                break

    filters: list[QueryFilter] = []
    if "critical" in tokens:
        filters.append(QueryFilter(field="severity", operator="=", value="critical"))
    elif "warning" in tokens:
        filters.append(QueryFilter(field="severity", operator="IN", value=("warning", "critical")))

    order_by: list[QueryOrder] = []
    if measure in {"count", "avg", "max", "min", "sum"}:
        order_by.append(QueryOrder(field=measure, direction="desc"))
    elif entity.time_field:
        order_by.append(QueryOrder(field=entity.time_field, direction="desc" if measure != "trend" else "asc"))
    if measure == "latest":
        order_by = [QueryOrder(field=entity.time_field or "time", direction="desc")]

    if limit is None:
        if measure == "count":
            limit = 1
        elif entity.default_limit:
            limit = entity.default_limit
        else:
            limit = 100

    notes = tuple(note for note in (*measure_notes, *time_notes) if note)
    return QueryPlan(
        intent=query,
        entity=entity.name,
        table=entity.table,
        measure=measure,
        select_fields=tuple(dict.fromkeys(select_fields)),
        filters=tuple(filters),
        group_by=group_by,
        order_by=tuple(order_by),
        limit=limit,
        time_window=time_window,
        search_terms=tuple(tokens),
        notes=notes,
    )


def compile_query_plan(plan: QueryPlan, *, model: SemanticModel | None = None) -> CompiledQuery:
    semantic_model = model or load_semantic_model()
    entity = semantic_model.find_entity(plan.entity) or semantic_model.find_entity(plan.table)
    if entity is None:
        raise ValueError(f"unknown semantic entity: {plan.entity}")

    field_map = entity.field_map()
    select_parts: list[str] = []
    params: list[Any] = []
    warnings: list[str] = []

    if plan.measure == "count":
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")
        select_parts.append("COUNT(*) AS count")
    elif plan.measure == "avg":
        measure_field = field_map.get("value")
        if measure_field is None:
            raise ValueError(f"{entity.name} does not expose a value measure")
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")
        select_parts.append(f"AVG({measure_field.expression}) AS avg")
    elif plan.measure == "max":
        measure_field = field_map.get("value")
        if measure_field is None:
            raise ValueError(f"{entity.name} does not expose a value measure")
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")
        select_parts.append(f"MAX({measure_field.expression}) AS max")
    elif plan.measure == "min":
        measure_field = field_map.get("value")
        if measure_field is None:
            raise ValueError(f"{entity.name} does not expose a value measure")
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")
        select_parts.append(f"MIN({measure_field.expression}) AS min")
    elif plan.measure == "sum":
        measure_field = field_map.get("value")
        if measure_field is None:
            raise ValueError(f"{entity.name} does not expose a value measure")
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")
        select_parts.append(f"SUM({measure_field.expression}) AS sum")
    else:
        for name in plan.select_fields or (entity.time_field or "*",):
            if name == "*":
                select_parts.append("*")
                continue
            field = field_map.get(name)
            if field is None:
                warnings.append(f"field not found in semantic model: {name}")
                continue
            select_parts.append(field.expression if field.expression == field.name else f"{field.expression} AS {field.name}")

    sql = [f"SELECT {', '.join(select_parts) if select_parts else '*'}", f"FROM {entity.table}"]
    where_clauses: list[str] = []
    where_params: list[Any] = []

    for item in plan.filters:
        field = field_map.get(item.field)
        expression = field.expression if field else item.field
        operator = item.operator.upper()
        if operator == "IN":
            values = list(item.value if isinstance(item.value, (tuple, list)) else [item.value])
            if not values:
                continue
            placeholders = ", ".join(["%s"] * len(values))
            where_clauses.append(f"{expression} IN ({placeholders})")
            where_params.extend(values)
        elif operator in {"LIKE", "ILIKE"}:
            where_clauses.append(f"{expression} {operator} %s")
            where_params.append(item.value)
        else:
            where_clauses.append(f"{expression} {operator} %s")
            where_params.append(item.value)

    if plan.time_window and entity.time_field:
        kind = plan.time_window.get("kind")
        if kind == "relative":
            count = int(plan.time_window.get("count", 1))
            unit = str(plan.time_window.get("unit", "hour"))
            interval_unit = unit[:-1] if unit.endswith("s") else unit
            where_clauses.insert(0, f"{entity.time_field} >= NOW() - (%s * INTERVAL '1 {interval_unit}')")
            where_params.insert(0, count)

    if where_clauses:
        sql.append("WHERE " + " AND ".join(where_clauses))
        params.extend(where_params)

    if plan.group_by:
        group_parts: list[str] = []
        for name in plan.group_by:
            field = field_map.get(name)
            if field:
                group_parts.append(field.expression)
        if group_parts:
            sql.append("GROUP BY " + ", ".join(group_parts))

    if plan.order_by:
        order_parts: list[str] = []
        for item in plan.order_by:
            field = field_map.get(item.field)
            expression = field.expression if field else item.field
            direction = "DESC" if item.direction.lower() == "desc" else "ASC"
            order_parts.append(f"{expression} {direction}")
        if order_parts:
            sql.append("ORDER BY " + ", ".join(order_parts))

    if plan.limit > 0:
        sql.append("LIMIT %s")
        params.append(plan.limit)

    return CompiledQuery(sql="\n".join(sql), params=tuple(params), entity=entity.name, warnings=tuple(warnings))

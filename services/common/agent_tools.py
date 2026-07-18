from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
from pathlib import Path
from typing import Any

from services.analytics.reporting import report_engine
from services.assets.model import hierarchy_to_tree, load_hierarchy
from services.common.modeling import ModelRegistry
from services.common.semantic_store import get_semantic_store
from services.scenarios.engine import list_scenarios


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    read_only: bool
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    tags: tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.register(
            ToolSpec(
                name="historian.recent_events",
                description="Read recent historian events for a table.",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "table": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                    },
                    "required": ["table"],
                },
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("historian", "read_only", "events"),
            )
        )
        self.register(
            ToolSpec(
                name="historian.trend",
                description="Read a historical trend for an asset tag.",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "asset_id": {"type": "string"},
                        "tag": {"type": "string"},
                        "hours": {"type": "integer", "minimum": 1, "maximum": 168},
                    },
                    "required": ["asset_id", "tag"],
                },
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("historian", "read_only", "trend"),
            )
        )
        self.register(
            ToolSpec(
                name="historian.alarms",
                description="Read active or recent alarms.",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                    },
                },
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("historian", "read_only", "alarms"),
            )
        )
        self.register(
            ToolSpec(
                name="assets.hierarchy",
                description="Read the configured asset hierarchy.",
                read_only=True,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("assets", "read_only"),
            )
        )
        self.register(
            ToolSpec(
                name="reports.templates",
                description="Read report templates available to operators.",
                read_only=True,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("reports", "read_only"),
            )
        )
        self.register(
            ToolSpec(
                name="scenarios.list",
                description="Read available replay scenarios.",
                read_only=True,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("replay", "read_only"),
            )
        )
        self.register(
            ToolSpec(
                name="semantic.graph_search",
                description="Search the semantic graph for entities and relationships.",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 100},
                        "site_id": {"type": "string"},
                    },
                    "required": ["query"],
                },
                output_schema={"type": "object"},
                tags=("semantic", "read_only", "graph"),
            )
        )
        self.register(
            ToolSpec(
                name="semantic.lineage",
                description="Read semantic lineage records.",
                read_only=True,
                input_schema={
                    "type": "object",
                    "properties": {
                        "site_id": {"type": "string"},
                        "limit": {"type": "integer", "minimum": 1, "maximum": 1000},
                    },
                },
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("semantic", "read_only", "lineage"),
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)


tool_registry = ToolRegistry()


def _validate_tool_arguments(spec: ToolSpec, arguments: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    schema = spec.input_schema
    properties = schema.get("properties", {})
    unknown = sorted(set(arguments) - set(properties))
    if unknown:
        raise ValueError(f"unsupported arguments for {spec.name}: {', '.join(unknown)}")
    missing = [name for name in schema.get("required", []) if name not in arguments]
    if missing:
        raise ValueError(f"missing required arguments for {spec.name}: {', '.join(missing)}")
    result = dict(arguments)
    defaults = {"limit": 25, "hours": 6, "table": "industrial_events"}
    for key, value in defaults.items():
        if key in properties and key not in result:
            result[key] = value
    for key, definition in properties.items():
        if key not in result:
            continue
        value = result[key]
        if definition.get("type") == "integer":
            if isinstance(value, bool):
                raise ValueError(f"{key} must be an integer")
            result[key] = int(value)
            if "minimum" in definition and result[key] < definition["minimum"]:
                raise ValueError(f"{key} is below the allowed minimum")
            if "maximum" in definition and result[key] > definition["maximum"]:
                raise ValueError(f"{key} is above the allowed maximum")
        elif definition.get("type") == "string" and not isinstance(value, str):
            raise ValueError(f"{key} must be a string")
    return result


def _execute_tool(name: str, arguments: dict[str, Any]) -> Any:
    if name == "historian.recent_events":
        return query_recent_events(arguments["table"], arguments["limit"])
    if name == "historian.trend":
        return query_trend(arguments["asset_id"], arguments["tag"], arguments["hours"])
    if name == "historian.alarms":
        return query_alarms(arguments.get("limit", 25))
    if name == "assets.hierarchy":
        return hierarchy_to_tree(load_hierarchy(Path("config/assets.yaml")))
    if name == "reports.templates":
        return report_engine.list_templates()
    if name == "scenarios.list":
        return list_scenarios()
    if name == "semantic.graph_search":
        graph = get_semantic_store().graph()
        return graph.graph_search(arguments["query"], limit=arguments.get("limit", 25), site_id=arguments.get("site_id"))
    if name == "semantic.lineage":
        from services.historian.client import list_semantic_lineage

        return list_semantic_lineage(site_id=arguments.get("site_id"), limit=arguments.get("limit", 25))
    raise ValueError(f"unknown read-only tool: {name}")


def execute_read_only_tool(name: str, arguments: dict[str, Any], *, timeout_seconds: float = 10.0) -> Any:
    """Validate and execute one registered read-only tool with a hard wait bound."""

    spec = tool_registry.get(name)
    if spec is None or not spec.read_only:
        raise ValueError(f"tool is not registered as read-only: {name}")
    validated = _validate_tool_arguments(spec, arguments)
    timeout = min(max(float(timeout_seconds), 0.1), 30.0)
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="agent-readonly") as executor:
        future = executor.submit(_execute_tool, name, validated)
        try:
            return future.result(timeout=timeout)
        except FutureTimeoutError as exc:
            future.cancel()
            raise TimeoutError(f"read-only tool timed out after {timeout:g}s: {name}") from exc


def query_alarms(limit: int) -> list[dict[str, Any]]:
    try:
        from services.historian.client import query_alarms

        return query_alarms(limit)
    except Exception:
        return []


def query_recent_events(table: str, limit: int) -> list[dict[str, Any]]:
    try:
        from services.historian.client import query_recent_events

        return query_recent_events(table, limit)
    except Exception:
        return []


def query_trend(asset_id: str, tag: str, hours: int) -> list[dict[str, Any]]:
    try:
        from services.historian.client import query_trend

        return query_trend(asset_id, tag, hours)
    except Exception:
        return []


def build_context_package(
    *,
    asset_id: str | None = None,
    tag: str | None = None,
    limit: int = 25,
    hours: int = 6,
    table: str = "industrial_events",
    site_profile_path: Path | str | None = None,
) -> dict[str, Any]:
    assets = hierarchy_to_tree(load_hierarchy(Path("config/assets.yaml")))
    semantic_store = get_semantic_store()
    semantic_graph = semantic_store.graph()
    context: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": {
            "asset_id": asset_id,
            "tag": tag,
            "limit": limit,
            "hours": hours,
            "table": table,
        },
        "alarms": query_alarms(limit),
        "events": query_recent_events(table, limit),
        "assets": assets,
        "scenarios": list_scenarios(),
        "report_templates": report_engine.list_templates(),
        "read_only_tools": tool_registry.list_tools(),
        "model_roles": ModelRegistry.from_env().export(),
        "semantic": {
            "counts": semantic_graph.counts(),
            "ontology_packs": [pack.to_dict() for pack in semantic_graph.ontology_packs],
        },
    }
    if asset_id and tag:
        context["trend"] = query_trend(asset_id, tag, hours)
        context["semantic"]["matches"] = semantic_graph.graph_search(f"{asset_id} {tag}", limit=limit)
    if site_profile_path is not None:
        from services.common.site_profiles import load_site_profile, validate_site_profile

        profile = load_site_profile(site_profile_path)
        context["site_profile"] = profile.to_dict()
        context["site_profile_validation"] = validate_site_profile(profile)
        context["model_roles"] = ModelRegistry.from_site_profile(profile).export()
        site_id = profile.site.id if getattr(profile, "site", None) else None
        if site_id:
            context["semantic"]["site_id"] = site_id
            context["semantic"]["site_matches"] = semantic_graph.graph_search(site_id, limit=limit, site_id=site_id)
    return context

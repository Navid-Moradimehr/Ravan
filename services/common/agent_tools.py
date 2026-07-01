from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.analytics.reporting import report_engine
from services.assets.model import hierarchy_to_tree, load_hierarchy
from services.common.modeling import ModelRegistry
from services.historian.client import query_alarms, query_recent_events, query_trend
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
                description="Read available simulation scenarios.",
                read_only=True,
                input_schema={"type": "object", "properties": {}},
                output_schema={"type": "array", "items": {"type": "object"}},
                tags=("simulation", "read_only"),
            )
        )

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [tool.to_dict() for tool in self._tools.values()]

    def get(self, name: str) -> ToolSpec | None:
        return self._tools.get(name)


tool_registry = ToolRegistry()


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
    }
    if asset_id and tag:
        context["trend"] = query_trend(asset_id, tag, hours)
    if site_profile_path is not None:
        from services.common.site_profiles import load_site_profile, validate_site_profile

        profile = load_site_profile(site_profile_path)
        context["site_profile"] = profile.to_dict()
        context["site_profile_validation"] = validate_site_profile(profile)
        context["model_roles"] = ModelRegistry.from_site_profile(profile).export()
    return context


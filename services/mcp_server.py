"""Ravan's external-agent MCP server.

The MCP surface is an adapter over the existing diagnostic registry and
assistant action ledger.  It does not create a second business-logic API.
"""
from __future__ import annotations

import argparse
import asyncio
import os
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from services.common.agent_runtime import DiagnosticAgentRuntime

SERVER_INSTRUCTIONS = (
    "Ravan exposes bounded industrial telemetry, lineage, governance, and source tools. "
    "Use read tools for analysis. For changes, call ravan_action_prepare, show the exact "
    "preview, then call ravan_action_confirm only when the user has approved it. "
    "Never request or return credentials, private keys, or raw secret values."
)

READ_TOOLS = {
    "sources_list": "sources.list",
    "governance_snapshot": "governance.snapshot",
    "historian_recent_events": "historian.recent_events",
    "historian_trend": "historian.trend",
    "historian_alarms": "historian.alarms",
    "assets_hierarchy": "assets.hierarchy",
    "reports_templates": "reports.templates",
    "scenarios_list": "scenarios.list",
    "semantic_graph_search": "semantic.graph_search",
    "semantic_lineage": "semantic.lineage",
}


def _actor() -> str:
    return os.getenv("RAVAN_MCP_ACTOR_ID", "external-agent").strip() or "external-agent"


def _site() -> str:
    return os.getenv("RAVAN_MCP_SITE_ID", "").strip()


def build_mcp_server(*, allow_write: bool | None = None) -> FastMCP:
    """Build an isolated server instance for stdio, HTTP, and tests."""

    writes_enabled = bool(
        os.getenv("RAVAN_MCP_ALLOW_WRITE", "false").lower() in {"1", "true", "yes", "on"}
        if allow_write is None
        else allow_write
    )
    server = FastMCP(
        "Ravan",
        instructions=SERVER_INSTRUCTIONS,
        host=os.getenv("RAVAN_MCP_HOST", "127.0.0.1"),
        port=int(os.getenv("RAVAN_MCP_PORT", "8030")),
        streamable_http_path="/",
        json_response=True,
        stateless_http=True,
    )

    def read_tool(tool_name: str, arguments: dict[str, Any]) -> Any:
        runtime = DiagnosticAgentRuntime(actor_id=_actor(), site_id=_site())
        result = runtime.dispatch_tool(
            call_id=f"mcp-{tool_name}",
            tool_name=tool_name,
            arguments=arguments,
            metadata={"transport": "mcp", "client_actor": _actor()},
        )
        if result.get("status") != "succeeded":
            raise RuntimeError(str(result.get("error") or result.get("status")))
        return result.get("result")

    read_annotations = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    write_annotations = ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=False, openWorldHint=True)

    @server.tool(name="sources_list", annotations=read_annotations)
    def sources_list(site_id: str = "") -> Any:
        """List configured source connections without credential values."""
        return read_tool(READ_TOOLS["sources_list"], {"site_id": site_id or _site()})

    @server.tool(name="governance_snapshot", annotations=read_annotations)
    def governance_snapshot() -> Any:
        """Read active assistant and action governance."""
        return read_tool(READ_TOOLS["governance_snapshot"], {})

    @server.tool(name="historian_recent_events", annotations=read_annotations)
    def historian_recent_events(table: str = "industrial_events", limit: int = 25) -> Any:
        """Read a bounded recent event window."""
        return read_tool(READ_TOOLS["historian_recent_events"], {"table": table, "limit": limit})

    @server.tool(name="historian_trend", annotations=read_annotations)
    def historian_trend(asset_id: str, tag: str, hours: int = 6) -> Any:
        """Read a bounded historical trend."""
        return read_tool(READ_TOOLS["historian_trend"], {"asset_id": asset_id, "tag": tag, "hours": hours})

    @server.tool(name="historian_alarms", annotations=read_annotations)
    def historian_alarms(limit: int = 25) -> Any:
        """Read active or recent alarms."""
        return read_tool(READ_TOOLS["historian_alarms"], {"limit": limit})

    @server.tool(name="assets_hierarchy", annotations=read_annotations)
    def assets_hierarchy() -> Any:
        """Read the configured asset hierarchy."""
        return read_tool(READ_TOOLS["assets_hierarchy"], {})

    @server.tool(name="reports_templates", annotations=read_annotations)
    def reports_templates() -> Any:
        """List available report templates."""
        return read_tool(READ_TOOLS["reports_templates"], {})

    @server.tool(name="scenarios_list", annotations=read_annotations)
    def scenarios_list() -> Any:
        """List deterministic replay scenarios."""
        return read_tool(READ_TOOLS["scenarios_list"], {})

    @server.tool(name="semantic_graph_search", annotations=read_annotations)
    def semantic_graph_search(query: str, limit: int = 25, site_id: str = "") -> Any:
        """Search the semantic graph with a bounded result count."""
        return read_tool(READ_TOOLS["semantic_graph_search"], {"query": query, "limit": limit, "site_id": site_id or _site()})

    @server.tool(name="semantic_lineage", annotations=read_annotations)
    def semantic_lineage(site_id: str = "", limit: int = 25) -> Any:
        """Read semantic lineage records."""
        return read_tool(READ_TOOLS["semantic_lineage"], {"site_id": site_id or _site(), "limit": limit})

    @server.resource("ravan://capabilities")
    def capabilities() -> str:
        from services.common.agent_runtime import build_agent_runtime_contract
        import json

        return json.dumps({"mcp_write_enabled": writes_enabled, **build_agent_runtime_contract()}, default=str)

    @server.resource("ravan://source-catalog")
    def source_catalog() -> str:
        from services.common.device_compat import DEVICE_PROFILES, PROTOCOL_PROFILES
        import json

        return json.dumps({"protocols": list(PROTOCOL_PROFILES), "device_profiles": DEVICE_PROFILES}, default=str)

    @server.resource("ravan://governance")
    def governance_resource() -> str:
        import json
        from services.common.governance_plane import build_governance_snapshot

        return json.dumps(build_governance_snapshot(), default=str)

    @server.prompt(name="diagnose_source")
    def diagnose_source(connection_id: str) -> str:
        """Create a bounded source diagnostic workflow for an agent."""
        return f"Inspect source {connection_id}: list its metadata, review governance, then report health and next safe steps. Do not expose credentials."

    if writes_enabled:
        @server.tool(name="ravan_action_prepare", annotations=write_annotations)
        async def ravan_action_prepare(action_name: str, target_resource: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
            """Prepare an exact action preview; no industrial change occurs."""
            from services.api_service.routers.assistant import ActionPreviewRequest, preview_action

            return await preview_action(ActionPreviewRequest(actor_id=_actor(), action_name=action_name, target_resource=target_resource, details=details or {}))

        @server.tool(name="ravan_action_confirm", annotations=write_annotations)
        async def ravan_action_confirm(intent_id: str, confirmation_token: str) -> dict[str, Any]:
            """Execute a previously previewed action using its single-use token."""
            from services.api_service.routers.assistant import ActionConfirmRequest, confirm_action

            return await confirm_action(intent_id, ActionConfirmRequest(actor_id=_actor(), confirmation_token=confirmation_token))

        @server.tool(name="ravan_action_reject", annotations=write_annotations)
        async def ravan_action_reject(intent_id: str) -> dict[str, Any]:
            """Reject a pending action preview."""
            from services.api_service.routers.assistant import ActionDecisionRequest, reject_action

            return await reject_action(intent_id, ActionDecisionRequest(actor_id=_actor()))

    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Expose Ravan through MCP")
    parser.add_argument("serve", nargs="?", default="serve")
    parser.add_argument("--transport", choices=("stdio", "streamable-http"), default="stdio")
    parser.add_argument("--allow-write", action="store_true", help="Expose approval-gated action tools")
    args = parser.parse_args()
    server = build_mcp_server(allow_write=args.allow_write)
    if args.transport == "streamable-http":
        asyncio.run(server.run_streamable_http_async())
    else:
        asyncio.run(server.run_stdio_async())


if __name__ == "__main__":
    main()

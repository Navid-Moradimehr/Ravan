from services.mcp_server import build_mcp_server


def test_mcp_read_surface_is_bounded_and_write_opt_in():
    read_only = build_mcp_server(allow_write=False)
    trusted = build_mcp_server(allow_write=True)
    read_names = {tool.name for tool in read_only._tool_manager.list_tools()}
    trusted_names = {tool.name for tool in trusted._tool_manager.list_tools()}
    assert "sources_list" in read_names
    assert "ravan_action_confirm" not in read_names
    assert {"ravan_action_prepare", "ravan_action_confirm", "ravan_action_reject"}.issubset(trusted_names)


def test_mcp_read_tool_uses_existing_registry(monkeypatch):
    monkeypatch.setattr(
        "services.mcp_server.DiagnosticAgentRuntime.dispatch_tool",
        lambda self, **kwargs: {"status": "succeeded", "result": [{"connection_id": "c-1"}]},
    )
    server = build_mcp_server(allow_write=False)
    tool = server._tool_manager._tools["sources_list"]
    result = tool.fn(site_id="plant-a")
    assert result == [{"connection_id": "c-1"}]


def test_mcp_instructions_preserve_safe_action_workflow():
    server = build_mcp_server(allow_write=True)
    assert "ravan_action_prepare" in server.instructions
    assert "Never request or return credentials" in server.instructions

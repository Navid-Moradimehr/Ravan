# External Agent Integration through MCP

Ravan exposes its platform contracts as an MCP server. External agents remain
user-owned: Codex, Claude Code, Hermes, Omnigent and compatible OpenClaw
versions provide the model, orchestration and permission interface.

## Transports

- Local-first: `ravan-mcp serve --transport stdio`
- Deployed: Streamable HTTP at `/mcp`, mounted by the API service

HTTP is loopback/read-only by default. A deployment must explicitly set
`RAVAN_MCP_ALLOW_WRITE=true` to advertise action tools. Authentication and
actor/site mapping remain deployment-owned, consistent with Ravan's existing
authentication boundary.

## Tools and resources

The read-only surface includes sources, governance, historian events/trends/
alarms, assets, reports, scenarios, semantic search and lineage. Resources
include `ravan://capabilities`, `ravan://source-catalog` and
`ravan://governance`; `diagnose_source` provides a bounded workflow prompt.

When writes are enabled, the server exposes `ravan_action_prepare`,
`ravan_action_confirm` and `ravan_action_reject`. These call the existing
assistant action ledger and preserve preview, expiry, single-use token and
audit behavior. They do not expose secrets or direct PLC/actuator control.

Client-side approval is separate from deployment authentication. A safe client
configuration allows only read tools. A trusted task may permanently allow the
Ravan MCP namespace in the external agent interface, subject to the deployment
credential's actor/site scope and Ravan's action ledger.

## Compatibility examples

Codex uses a Streamable HTTP URL or stdio command in its MCP configuration and
supports per-server enabled/disabled tools and approval modes. Claude Code uses
`mcp__ravan__*` permission rules. Hermes uses `mcp_servers` with tool include
lists. Omnigent declares Ravan as an MCP tool provider in its agent YAML.
Use an isolated configuration for tests; never commit credentials.

## Verification

Run the focused contract tests first:

```text
python -m pytest -q tests/test_mcp_server.py tests/test_versal_contract.py
```

The combined 15-minute profile is
`config/benchmarks/versal-mcp-soak.yaml`. It requires dual Sparkplug/OPC UA
telemetry, reconnect and restart coverage, zero unaccounted events/DLQ/errors,
and a local MCP read p95 below two seconds.

# Agent Governance Boundary

The platform supplies infrastructure for user-connected agents, not a
general-purpose autonomous agent. The built-in diagnostic path is read-only;
the supervised-action path records requests and approvals but never executes a
PLC, connector, or external write.

## Read-only dispatch

`POST /api/v1/modeling/diagnostic/dispatch` accepts an actor, tool name,
arguments, and an optional timeout. The platform checks that the tool is in
the read-only registry, validates required fields and numeric bounds, rejects
unknown arguments, limits the wait to 30 seconds, and writes an audit event for
success, failure, or approval-required status.

Current tools are historian events/trend/alarms, asset hierarchy, report
templates, scenarios, semantic graph search, and semantic lineage. The
runtime does not accept connector writes, arbitrary SQL, shell commands, or
PLC operations through this endpoint.

## Supervised-action request ledger

`POST /api/v1/modeling/agent-actions` creates a durable `pending_approval`
request. Operators can list requests and explicitly approve, reject, or cancel
them through the action endpoints. Those decisions are audited and persisted
to the existing API data volume. Approval is a governance record only; a user
or separately deployed action executor must implement the actual operation
behind its own safety boundary.

If audit persistence fails, the request/dispatch returns an error instead of
silently claiming that governance evidence exists. The Timescale migration
creates the `audit_logs` table for fresh and existing deployments.

## User-owned extensions

Users still own agent system prompts, skills, MCP servers, model selection,
identity policy, approval personnel, tool-specific authorization, and any
action executor. The platform's contracts make those integrations explicit
without forcing one agent framework or cloud provider.

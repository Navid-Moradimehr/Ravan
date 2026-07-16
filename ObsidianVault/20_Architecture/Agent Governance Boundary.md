# Agent Governance Boundary

## Platform-owned

- Read-only tool registry and schema validation.
- Bounded dispatch timeout and unknown-argument rejection.
- Audit records for successful, failed, and approval-required calls.
- Durable supervised-action request ledger with pending/approved/rejected/
  cancelled states.
- No autonomous PLC or connector writes.

## User-owned

Users provide agents, MCP servers, skills, prompts, identity integration,
approval policy, action executor, and operational safety controls. Approval in
the platform is not execution.

## API

- `POST /api/v1/modeling/diagnostic/dispatch`
- `GET/POST /api/v1/modeling/agent-actions`
- `POST /api/v1/modeling/agent-actions/{action_id}/{approve|reject|cancel}`

Audit persistence is fail-visible. The API data volume stores the action
ledger; TimescaleDB stores audit events.

[[Model Lifecycle Ledger]]
[[Production Readiness Action Plan]]

# Agent Integration Guidance

The platform should not become a general agent framework.

## What the platform should own

- read-only tool schemas
- agent runtime contracts
- diagnostic read-only policy
- supervised-action approval policy
- audit logging for agent tool calls and action requests
- prompt registry entries for the platform-owned diagnostic scaffold
- governance snapshot visibility over the contracts above

## What users should own

- their own agents
- their own MCP servers
- their own skill packs
- their own orchestration/runtime layer
- their own action execution semantics
- their own company-specific prompts for proprietary workflows

## Recommendation

Ship stable platform contracts and a small number of vetted diagnostic prompt scaffolds.
Do not ship a generic skills marketplace or a broad MCP integration framework in the core.

Why:

- skills and MCP routing are highly environment-specific
- users will need to map them to their own tools, policies, and data boundaries
- a core skills system would widen the platform before the governance layer is ready

The right model is:

- platform = contracts + audit + read-only scaffolds
- users = agents + skills + orchestration + MCP integrations

## Practical implication

If a user wants an agent that reasons over historian data, alarms, reports, and assets, the platform should give them:

- typed read-only APIs
- a diagnostic prompt scaffold
- governance snapshots
- audit events

The user should then connect their own model server, skills, and MCP server to those APIs.


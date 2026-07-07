# Agent Integration Guidance

The platform should own contracts, not a general-purpose agent ecosystem.

## Platform-owned

- read-only tool schemas
- agent runtime contracts
- diagnostic read-only policy
- supervised-action approval policy
- audit logging for tool calls and action requests
- prompt registry entries for platform-owned diagnostic scaffolds
- governance snapshot visibility

## User-owned

- agents
- MCP servers
- skill packs
- orchestration runtime
- action execution semantics
- company-specific prompts

## Recommendation

Keep the platform narrow:

- core = contracts + audit + read-only scaffolds
- users = their own agents, skills, MCP, and orchestration

Do not add a general skills framework or skills marketplace to the core.


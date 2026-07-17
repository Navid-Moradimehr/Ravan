# Ravan Vault

Open this folder as an Obsidian vault to track product reasoning, architecture decisions, runbooks, and UI notes.

## Map

- `00_Inbox`: raw notes and temporary captures
- `10_PRD`: product requirements and scope
- `20_Architecture`: diagrams, data flow, service contracts
- `30_UI_UX`: dashboard screens, design tokens, interaction notes
- `40_Runbooks`: setup, debugging, recovery
- `50_ADR`: architecture decision records
- `60_Observability`: metrics, dashboards, alert semantics
- `90_Archives`: superseded notes

## Current AI Gateway

- [AI provider configuration](../docs/ai-provider-configuration.md): native cloud adapters, compatible gateways, deployment secrets, and report locations.
- [User-facing source and AI reporting](../docs/user-facing-source-and-ai-reporting.md): operator workflow and ownership boundaries.

The gateway supports named Anthropic and Gemini native APIs plus OpenAI,
DeepSeek, Qwen, Kimi, GLM, vLLM, LM Studio, Ollama, and other
OpenAI-compatible endpoints. Credentials remain deployment-owned. AI Reporting
shows durable job status; generated content is emitted to `iot.ai_enriched` and
stored in historian `ai_enriched`.

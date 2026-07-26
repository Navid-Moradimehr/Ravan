# Ravan Assistant Orchestration

Ravan uses a small, durable orchestration contract rather than a second
workflow engine. A chat turn is persisted as user and assistant messages. A
read request may dispatch a bounded diagnostic tool. A configuration request
becomes a typed action intent with an expiry, an exact preview, an audit record,
and an explicit confirmation. A question request pauses as a persisted
questionnaire and resumes through the question-answer route.

## CRM-inspired patterns

The CRM reference implementation uses a `pendingQuestionMessageId`, a typed
question payload, a question-answer mutation, and stream resumption after the
answer. It also separates skill discovery/loading from the agent's general
instructions and records workflow-run state for observability. Ravan now uses
the same important principles without importing CRM entities or dependencies:

- pending source questionnaires have an ID, expiry, status, typed fields, and
  persisted answers;
- answers are validated before the assistant resumes the draft;
- completed questionnaires cannot be answered again;
- action previews and approvals remain separate from read-only tool calls;
- skill files are versioned, declarative guidance packs, not executable code;
- every turn has a durable running, completed, or failed record;
- retryable provider failures expose a structured error and retry endpoint;
- diagnostic tool calls have a durable lifecycle record;
- the model prompt includes safety, untrusted-context, skill-selection, and
  failure-recovery instructions;
- external operator products remain guidance-only.

## Source onboarding lifecycle

1. The operator asks the assistant to connect or add a source.
2. The assistant asks for protocol, name, site, endpoint, and credential
   reference.
3. The drawer renders choice and text controls. Answers are persisted with the
   thread and expire after fifteen minutes.
4. Protocol-specific validation rejects malformed endpoints or secret values.
5. Ravan returns a source draft without saving or enabling it.
6. The operator opens Source connections, adds mappings and protocol-specific
   settings, validates, tests, and enables the source.

This boundary is deliberate. Industrial connector configuration cannot be
reliably inferred from a sentence, and a partial draft must not silently enter
the runtime.

## Skill ownership

The bundled `config/assistant-skills` files are safe baseline guidance. Users
may add company-specific skills in their deployment or adapt these files, but
the assistant loads them through the read-only skill registry and includes only
relevant content in model context. Skills do not execute code and do not bypass
API policy, source validation, confirmation, audit, or user-owned
authentication. `GET /api/v1/assistant/skills` lists available skill metadata;
the item route returns the declarative content.

## Current limits

## Model routing

The AI gateway exposes `GET /models` as a credential-free catalog. For an
OpenAI-compatible backend such as LM Studio, it discovers the model IDs from
the backend's `/v1/models` endpoint and always retains the configured model as
a fallback. The API exposes the same catalog at
`GET /api/v1/assistant/models`, and the dashboard proxies it at
`GET /api/assistant/models`.

Chat turns may include `context.model_id`. The API forwards that ID to the
provider-neutral gateway, and the gateway uses it in the provider request
without changing the configured provider or endpoint. This supports local
LM Studio, Ollama, and compatible cloud providers while keeping credentials
deployment-owned. If model discovery fails, the UI displays the configured
model and the assistant remains usable with that model.

For the local LM Studio setup, configure the AI gateway endpoint and model in
the deployment environment, for example `http://host.docker.internal:1234/v1`
and `openai/gpt-oss-20b`. Start the gateway, open the assistant, and select the
model from the Chat header. A model request still follows the normal assistant
error handling and retry lifecycle.

Interactive chat uses `POST /api/v1/assistant/threads/{thread_id}/messages/stream`
and the dashboard proxy at `/api/assistant/threads/{thread_id}/messages/stream`.
The stream emits `status`, `token`, `complete`, and `error` events. The API
persists the final user and assistant messages through the same durable store
used by non-streaming operations. Raw provider reasoning is not forwarded;
only safe progress status and answer text are exposed.

Ravan does not yet provide a distributed workflow queue or partial-output
replay after a disconnected browser. It does provide database-backed assistant
state for multi-replica conversation history and live SSE output for the active
browser connection. Queue-based long-running jobs and resumable partial output
remain later additions triggered by measured workload needs.

The multi-node deployment path must set the assistant store backend to the
shared PostgreSQL adapter and must not use the Compose JSON file from multiple
API replicas. The local JSON store remains the default for one-node installs.

Set `RAVAN_ASSISTANT_STORE_BACKEND=postgres` and provide the same PostgreSQL or
TimescaleDB connection settings to every API and assistant worker replica.
The adapter creates its small `ravan_assistant_records` table on first use and
stores threads, turns, tool calls, memory candidates, and action intents as
version-neutral JSON records. This is shared operational state, not historian
telemetry. The database, backups, retention, TLS, and identity boundary remain
operator-owned.

The drawer mirrors this boundary with active conversation management, new chat,
rename, archive, restore, and archived history. The last active thread ID is
remembered locally only as a selection pointer; message contents remain in the
assistant repository.

The assistant keeps tool progress separate from the final response. Successful
diagnostic work is persisted as bounded `metadata.progress` and rendered as a
faint evidence block; the final response remains Markdown-rendered content.
The UI intentionally does not expose private provider chain-of-thought.

The Chat header exposes **New chat** directly. Untitled threads receive an
immediate normalized first-message title. Ravan may refine that title through
the AI gateway in the background; the normalized excerpt remains the safe
fallback when the gateway is unavailable.
Destructive archive deletion uses an in-app confirmation dialog rather than a
browser-native prompt so the interaction remains consistent with Ravan's
theme and keyboard-accessible dialog semantics.

Conversation lifecycle endpoints are:

- `DELETE /api/v1/assistant/threads/{thread_id}` to archive a conversation.
- `POST /api/v1/assistant/threads/{thread_id}/restore` to restore it.
- `DELETE /api/v1/assistant/threads/{thread_id}/permanent` to permanently
  delete an already archived conversation and its assistant records.

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
skills do not bypass API policy, source validation, confirmation, audit, or
user-owned authentication.

## Current limits

Ravan does not yet provide a distributed workflow queue, database-backed
multi-replica assistant store, or full CRM-style streaming resume protocol.
The single-node implementation is durable and restart-safe for the current
scope; PostgreSQL-backed state and streaming resume should be added only when
multi-replica assistant usage becomes a measured requirement.
